/* Inline SVG illustrations (no image files needed). */
import { raw } from "./util.js";

export const heroArt = raw(`<svg viewBox="0 0 440 360" class="art" aria-hidden="true">
  <defs><linearGradient id="g1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity=".18"/><stop offset="1" stop-color="#ffffff" stop-opacity=".05"/></linearGradient></defs>
  <circle cx="300" cy="170" r="150" fill="url(#g1)"/><circle cx="300" cy="170" r="100" fill="url(#g1)"/>
  <g class="float"><rect x="150" y="70" width="210" height="140" rx="18" fill="#fff"/><rect x="170" y="92" width="96" height="10" rx="5" fill="#C75B0B"/><rect x="170" y="114" width="150" height="8" rx="4" fill="#dfe5ec"/><rect x="170" y="130" width="120" height="8" rx="4" fill="#dfe5ec"/>
  <rect x="170" y="156" width="64" height="26" rx="13" fill="#d6f0df"/><path d="M184 169l5 5 9-10" stroke="#1fa463" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/><circle cx="326" cy="172" r="22" fill="#C75B0B"/><path d="M316 172l7 7 13-14" stroke="#fff" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>
  <g class="float d2"><rect x="60" y="210" width="150" height="40" rx="20" fill="#fff"/><circle cx="84" cy="230" r="9" fill="#e3a008"/><rect x="102" y="222" width="90" height="8" rx="4" fill="#dfe5ec"/><rect x="102" y="235" width="60" height="6" rx="3" fill="#eef1f5"/></g>
  <g class="float d3"><rect x="250" y="250" width="160" height="40" rx="20" fill="#fff"/><circle cx="274" cy="270" r="9" fill="#d64545"/><rect x="292" y="262" width="100" height="8" rx="4" fill="#dfe5ec"/><rect x="292" y="275" width="64" height="6" rx="3" fill="#eef1f5"/></g>
  <path d="M120 120l60-30" stroke="#ffffff" stroke-opacity=".25" stroke-dasharray="4 6"/></svg>`);

export const loginArt = raw(`<svg viewBox="0 0 520 300" width="100%" style="max-width:520px;margin-top:24px" aria-hidden="true">
  <g class="float"><rect x="20" y="30" width="250" height="150" rx="18" fill="#fff"/><text x="42" y="64" style="font:700 14px Inter,sans-serif;fill:#17202a">Plans start at Rs. 499</text>
  <rect x="42" y="78" width="120" height="9" rx="4" fill="#dfe5ec"/><rect x="42" y="96" width="170" height="9" rx="4" fill="#dfe5ec"/><rect x="42" y="132" width="104" height="30" rx="15" fill="#d6f0df"/><text x="60" y="152" style="font:700 12px Inter,sans-serif;fill:#14693f">Valid · Pricing sheet v7</text></g>
  <g class="float d2"><rect x="230" y="110" width="250" height="150" rx="18" fill="#fff"/><text x="252" y="144" style="font:700 14px Inter,sans-serif;fill:#17202a">Used by 12,000+ customers</text>
  <rect x="252" y="158" width="150" height="9" rx="4" fill="#dfe5ec"/><rect x="252" y="212" width="170" height="30" rx="15" fill="#f8d9d9"/><text x="270" y="232" style="font:700 12px Inter,sans-serif;fill:#9b2a2a">Fact says 10,000+ · fix ready</text></g>
  <g class="float d3"><circle cx="440" cy="60" r="34" fill="#C75B0B"/><path d="M425 60l11 11 20-22" stroke="#fff" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g></svg>`);

export const emptyArt = raw(`<svg class="art" viewBox="0 0 160 110" aria-hidden="true"><rect x="38" y="14" width="84" height="84" rx="14" fill="var(--surface2)" stroke="var(--line)" stroke-width="2"/>
  <rect x="52" y="34" width="56" height="7" rx="3.5" fill="var(--line)"/><rect x="52" y="49" width="40" height="7" rx="3.5" fill="var(--line)"/><circle cx="104" cy="78" r="16" fill="#1fa463" opacity=".16"/>
  <path d="M96 78l6 6 11-12" stroke="#1fa463" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`);

export const okArt = raw(`<svg class="art" viewBox="0 0 160 110" aria-hidden="true"><circle cx="80" cy="55" r="38" fill="#1fa463" opacity=".14"/><circle cx="80" cy="55" r="26" fill="#1fa463"/>
  <path d="M68 56l8 8 16-17" stroke="#fff" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/><circle cx="30" cy="25" r="4" fill="#e3a008"/><circle cx="132" cy="30" r="5" fill="#C75B0B"/><circle cx="124" cy="92" r="4" fill="#2F6DB5"/><circle cx="36" cy="88" r="5" fill="#8a5cc2"/></svg>`);
