import type { ResearchArtifact } from '../lib/research-types';
import Icon from './Icon';

export function publicHttpUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try { const url = new URL(value, window.location.origin); return ['http:', 'https:'].includes(url.protocol) ? url.href : null; } catch { return null; }
}

export default function ResearchArtifacts({ artifacts }: { artifacts?: ResearchArtifact[] }) {
  if (!artifacts?.length) return null;
  return <section className="research-artifacts" aria-label="Downloadable research artifacts"><h4>Reproducible artifacts</h4><p>Download the recorded inputs and outputs. SHA-256 identifies the exact file.</p><ul>{artifacts.map((artifact) => {
    const url = publicHttpUrl(artifact.url);
    return <li key={artifact.id}><span className="artifact-file"><Icon name="reports" size={17} />{url ? <a href={url} download>{artifact.name}</a> : <span>{artifact.name} · Download unavailable</span>}{artifact.size_bytes !== undefined && <small>{(artifact.size_bytes / 1024).toLocaleString(undefined, { maximumFractionDigits: 1 })} KB</small>}</span><details><summary>File fingerprint</summary><code>{artifact.sha256}</code></details></li>;
  })}</ul></section>;
}
