# FinShield AI. Run `make help`.
STAGE      ?= dev
REGION     ?= ap-south-1
STACK      ?= finshield-$(STAGE)
ALERT_EMAIL ?= keshav.sharma@globalnodes.ai
MODE       ?= DRY_RUN
MODEL_ID   ?= mistral.mistral-large-3-675b-instruct
GUARDDUTY  ?= true
CONFIG_RECORDER ?= true
CONFIG_RULES ?= true
PY         := $(shell test -x .venv/bin/python && echo .venv/bin/python || echo python3)
PIP        := $(PY) -m pip
SAM        := $(shell test -x .venv/bin/sam && echo $(CURDIR)/.venv/bin/sam || echo sam)
LAYER      := build/layer
export AWS_DEFAULT_REGION := $(REGION)
export STACK STAGE REGION

.PHONY: help layer build validate deploy env seed scenario accuracy test smoke logs clean
help:
	@echo "make build               build layer + SAM artifacts"
	@echo "make validate            sam validate --lint"
	@echo "make deploy              deploy stack $(STACK) (ALERT_EMAIL=, MODE=LIVE|DRY_RUN, MODEL_ID=,"
	@echo "                          GUARDDUTY=, CONFIG_RECORDER=, CONFIG_RULES= true|false). SSM model/mode/email follow these."
	@echo "make env                 write web/.env.local from stack outputs"
	@echo "make seed                create Cognito demo users and load seed data"
	@echo "make scenario SC=SC-01   replay a scenario"
	@echo "make accuracy            run all scenarios (POST /accuracy/run equivalent)"
	@echo "make test                pytest"
	@echo "make smoke               end-to-end smoke test against the deployed stack"
	@echo "make logs FN=normalizer  tail a function's logs"

# Lambda layer: finshield package + contract data + arm64 Python deps
layer:
	rm -rf $(LAYER) && mkdir -p $(LAYER)/python
	cp -R backend/shared/python/finshield $(LAYER)/python/finshield
	find $(LAYER) -name __pycache__ -prune -exec rm -rf {} +
	mkdir -p $(LAYER)/python/finshield/contract
	cp contract/config.json $(LAYER)/python/finshield/contract/
	cp -R contract/schemas contract/fixtures $(LAYER)/python/finshield/contract/
	cp -R simulator/scenarios $(LAYER)/python/finshield/scenarios
	cp simulator/seed/generate.py $(LAYER)/python/finshield/seedgen.py
	cp simulator/seed/compliance_controls.json $(LAYER)/python/finshield/compliance_controls.json
	$(PIP) install --quiet --target $(LAYER)/python --platform manylinux2014_aarch64 --python-version 3.12 --implementation cp --only-binary=:all: --upgrade -r backend/shared/requirements.txt

build: layer
	cd infra && $(SAM) build --template-file template.yaml

validate:
	cd infra && $(SAM) validate --template-file template.yaml --lint --region $(REGION)

deploy: build
	cd infra && $(SAM) deploy --stack-name $(STACK) --parameter-overrides Stage=$(STAGE) AlertEmail=$(ALERT_EMAIL) ContainmentMode=$(MODE) BedrockModelId=$(MODEL_ID) CreateGuardDutyDetector=$(GUARDDUTY) CreateConfigRecorder=$(CONFIG_RECORDER) EnableConfigRules=$(CONFIG_RULES) $(EXTRA_PARAMS)

env:
	./scripts/write-env.sh

seed:
	./scripts/seed.sh

scenario:
	@test -n "$(SC)" || (echo "usage: make scenario SC=SC-01" && exit 2)
	./scripts/scenario.sh $(SC)

accuracy:
	./scripts/accuracy.sh

test:
	$(PY) -m pytest -q backend/tests

smoke:
	./scripts/smoke.sh

logs:
	@test -n "$(FN)" || (echo "usage: make logs FN=normalizer" && exit 2)
	aws logs tail /aws/lambda/finshield-$(STAGE)-$(subst _,-,$(FN)) --follow --since 10m --region $(REGION)

clean:
	rm -rf build infra/.aws-sam
