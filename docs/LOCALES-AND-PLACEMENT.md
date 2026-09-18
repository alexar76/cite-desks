# Languages and host placement

Cite desks are independent products. **Locale is not extra geography.** A Finnish UI does not license Swedish waters. A Dutch UI does not make Tideline a global flood index.

Canonical copy is English. Other languages are operator languages for the licensed evidence, not a claim expansion.

## Language sets

| Desk | Locales | Why these, not others |
|---|---|---|
| **Emberline** | `en`, `es`, `fr` | US fire ops + LatAm desks; EFFIS/southern-EU readers. Not `nl` (not a Rhine desk). Not `fi`. |
| **Tideline** | `en`, `nl`, `fr`, `de` | US CAP + EA English; RWS/Rhine NL; Hub'Eau FR; eHYD/PEGEL DE-AT. No Spanish: NWS CAP operators read English here. |
| **Solrecord** | `en`, `es`, `de` | NASA POWER (en); LatAm utility-scale; DACH PV. Not `fr` unless a France-plant desk is split later. |
| **Seamark** | `en`, `fi`, `nb` | International owners; Fintraffic; Kystverket (Bokmål). **No Swedish UI** — licensed waters are FI and NO, not Sweden. `no` Accept-Language maps to `nb`. |
| **Plinth** | `en`, `es`, `de` | US colo/campus EHS (en); LatAm sites; DACH campuses. Not `nl` (not a Rhine flood box). Not `fr` unless a France-campus desk is split later. |

Online guides:

| Desk | URL |
|---|---|
| Emberline | https://emberlinedesk.com/guide |
| Tideline | https://tidelinedesk.com/guide (local: `/guide`) |
| Solrecord | `/guide` on the Solrecord origin |
| Seamark | https://seamarkdesk.com/guide |
| Plinth | https://plinthdesk.com/guide |

Kernel API: `GET /api/public/i18n?lang=nl` and `GET /api/public/guide?lang=nl`. `Accept-Language` and cookie `desk_lang` also work. Emberline uses the React catalog (`src/lib/i18n.ts`).

## Hosts: USA vs Netherlands

The fleet has a **Metis demo host** (public demos, including Emberline demo), a **US box** (`attested` — Attested Memory only), and a **Netherlands box**. Placement follows evidence gravity + GDPR, not “one VPS for everything.” Do not put cite-desk demo on Attested Memory.

| Desk | Region | Host | Why |
|---|---|---|---|
| **Emberline (demo)** | fire SKUs still US-weighted | Metis (`emberlinedesk.com`) | Public demo, checkout closed. Family landing: `desks.modelmarket.dev`. Not Attested Memory, not Gitea. |
| **Solrecord** | **US** | listed on `desks.modelmarket.dev`; do not park on Attested | NASA POWER is US-published. Plant pins for US utilities are the lead. CAMS is EU but the SKU is ATLAS. |
| **Plinth** | **US** | listed on `desks.modelmarket.dev`; do not park on Attested | Colo and campus buyers are US-weighted (Ashburn / Northern Virginia). Public weather+air nowcasts, not a Rhine flood box. |
| **Tideline** | **NL** | Netherlands host | RWS, Rhine, Hub'Eau, eHYD, EA are EEA. US CAP still works from Amsterdam. Flood briefs stay in the Union. |
| **Seamark** | **NL** | Netherlands host | Fintraffic + Kystverket are EEA; AIS positions; GDPR; RTT to Helsinki/Oslo. **Do not** colocate with Emberline on the US fire box. |

Hub SKUs stay on ATLAS/GAIA wherever those already run. Desks are Hub *clients*. Do not run a second unofficial Hub on the desk host.

### What not to do

- Do not put Seamark or Tideline on Metis or Attested “because compose is already there.”
- Do not put the Emberline **demo** on Attested Memory. Metis is the public-demo host.
- Do not add a language to paper over a missing licence (Swedish UI ≠ Swedish AIS).

DNS: apex A/AAAA to the chosen host; TLS on that host. Sibling ports stay `127.0.0.1` behind nginx, same contour as Emberline.
