'use client';
import type { Who } from '@/lib/people';
import { avColor, initials } from '@/lib/format';

export function WhoCell({ who, size = 30 }: { who: Who; size?: number }) {
  return (
    <div className="who" style={{ minWidth: 0 }}>
      <div className="av" style={{ background: who.system ? '#334155' : avColor(who.name), color: who.system ? '#cbd5e1' : undefined, width: size, height: size, fontSize: 11 }}>
        {who.system ? '⚙' : initials(who.name)}</div>
      <div style={{ minWidth: 0 }}><div className="ellip" title={who.name}>{who.name}</div>{who.sub && <div className="dim ellip" style={{ fontSize: 11.5 }}>{who.sub}</div>}</div>
    </div>
  );
}
