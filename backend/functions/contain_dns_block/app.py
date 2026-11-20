"""contain_dns_block: add the alert's external destination to the DNS Firewall block list.

The destination comes from the S4 signal facts. Without DNS Firewall (EnableDnsFirewall=false)
the call is recorded as DRY_RUN. Release removes the domain again.
"""
import os

from finshield import containment

ACTION = "DNS_BLOCK"


def destinations(alert):
    out = []
    for s in alert.get("signals") or []:
        d = (s.get("facts") or {}).get("destination")
        if d and d not in out:
            out.append(d)
    return out


def plan(principal, ctx, event):
    domains = destinations(ctx["alert"])
    if not domains:
        return containment.Plan(not_applicable="no external destination in this alert")
    list_id = os.environ.get("DNS_DOMAIN_LIST_ID") or "<dns-firewall-domain-list-id>"
    c = containment.call("route53resolver", "update_firewall_domains", FirewallDomainListId=list_id, Operation="ADD", Domains=domains)
    plan_ = containment.Plan(calls=[c], detail={"domains": domains})
    if not os.environ.get("DNS_DOMAIN_LIST_ID"):
        plan_.detail["dns_firewall"] = "not enabled; recorded as DRY_RUN"
    return plan_


def handler(event, context):
    if not os.environ.get("DNS_DOMAIN_LIST_ID"):
        event = {**event, "force_dry_run": True}
    return containment.contain(ACTION, event, plan, actor="contain_dns_block")
