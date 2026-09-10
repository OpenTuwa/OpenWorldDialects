import sqlite3
import os
import subprocess
import time

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DB_PATH = "master_arabic_roots_backend.sqlite"
ROOTS_PER_VOLUME = 5

def cleanup_zombies():
    try:
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
        time.sleep(1)
    except Exception:
        pass

def safe_build():
    cleanup_zombies()

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Cannot find {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM roots ORDER BY id")
    roots = cursor.fetchall()
    total_roots = len(roots)
    total_volumes = (total_roots + ROOTS_PER_VOLUME - 1) // ROOTS_PER_VOLUME

    print(f"[*] Total Database Roots: {total_roots}")
    print(f"[*] Total Volumes: {total_volumes} ({ROOTS_PER_VOLUME} roots per book)")
    
    print("\nOperational Mode:")
    print("  1. Test Run (Build Volume 1 only)")
    print("  2. Build Range (e.g., Volumes 1 to 5)")
    print("  3. Build ALL")
    choice = input("Select option (1, 2, or 3): ").strip()

    if choice == "1":
        vol_range = range(0, 1)
    elif choice == "2":
        start_v = int(input("Start Volume: ").strip()) - 1
        end_v = int(input("End Volume: ").strip())
        vol_range = range(max(0, start_v), min(total_volumes, end_v))
    else:
        vol_range = range(0, total_volumes)

    persons_map = {
        "1s": "I (Me)", "1p": "We (Us)",
        "2ms": "You (Male)", "2fs": "You (Female)", "2p": "You All (Plural)",
        "3ms": "He (Him)", "3fs": "She (Her)", "3p": "They (Them)"
    }
    
    aspects_order = ["past", "present", "future", "progressive", "imperative"]
    aspects_map = {
        "past": "Past Tense<br><span class='sub-head'>(Completed Action)</span>",
        "present": "Present Tense<br><span class='sub-head'>(General / Habitual)</span>",
        "future": "Future Tense<br><span class='sub-head'>(Will Do Later)</span>",
        "progressive": "Progressive<br><span class='sub-head'>(Doing Right Now)</span>",
        "imperative": "Imperative<br><span class='sub-head'>(Command / Order)</span>"
    }

    nominals_map = {
        "Active Participle": "Active Participle (The Doer / Doing)",
        "Passive Participle": "Passive Participle (The Receiver / Done to)",
        "Noun Of Place": "Noun of Place (Location of Action)",
        "Noun Of Tool": "Noun of Tool (Instrument Used)",
        "Masdar": "Masdar (The Core Concept / Verbal Noun)",
        "Mnemonic": "Mnemonic (Memory Aid Device)"
    }

    css = """
    @page { size: A4 portrait; margin: 8mm 6mm; }
    * { box-sizing: border-box; }
    body { font-family: "Segoe UI", Roboto, Arial, sans-serif; font-size: 7.5pt; line-height: 1.1; margin: 0; color: #000; }
    @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } .page-break { page-break-before: always; } .avoid-break { page-break-inside: avoid; } }
    
    h1 { font-size: 14pt; text-align: center; border-bottom: 3px solid #000; margin: 0 0 10px 0; text-transform: uppercase; font-weight: 900; }
    .root-header { background: #1a1a1a; color: #fff; padding: 6px; margin: 10px 0 5px 0; font-size: 11pt; border: 1px solid #000; }
    .root-header .ar { float: right; font-size: 14pt; font-weight: bold; }
    .root-meaning { font-size: 8.5pt; margin: 0 0 8px 0; padding: 4px; border-left: 3px solid #000; background: #f0f0f0; }
    
    h3 { font-size: 9pt; margin: 8px 0 2px 0; text-transform: uppercase; border-bottom: 1px solid #666; }
    .sub-head { font-size: 6pt; font-weight: normal; color: #444; }

    table { width: 100%; border-collapse: collapse; margin-bottom: 8px; table-layout: fixed; }
    th { background: #333; color: #fff; border: 1px solid #000; padding: 4px 2px; text-align: center; font-size: 7pt; }
    td { border: 1px solid #000; vertical-align: top; padding: 0; }
    .row-header { background: #e8e8e8; font-weight: bold; text-align: center; vertical-align: middle; padding: 2px; border: 1px solid #000; }

    .dicho-cell { display: flex; flex-direction: column; width: 100%; height: 100%; }
    .dicho-half { display: flex; justify-content: space-between; align-items: center; padding: 2.5px 3px; min-height: 20px; }
    .aff { background: #ffffff; border-bottom: 1px dotted #888; }
    .neg { background: #eeeeee; }
    
    .sign { font-weight: bold; font-size: 8pt; width: 8px; }
    .sign.plus { color: #000; }
    .sign.minus { color: #444; }
    
    .en { font-family: "Consolas", monospace; font-size: 6.5pt; flex-grow: 1; padding-left: 3px; text-align: left; }
    .ar { font-family: "Arial", sans-serif; font-size: 8.5pt; font-weight: bold; direction: rtl; text-align: right; }
    
    .na { background: #dcdcdc; color: #777; text-align: center; vertical-align: middle; font-size: 6.5pt; font-style: italic; padding: 8px; }
    
    .dialect-bar { background: #444; color: #fff; padding: 4px; font-weight: bold; font-size: 8pt; text-transform: uppercase; border: 1px solid #000; margin-top: 5px; }
    """

    for vol_idx in vol_range:
        vol_num = vol_idx + 1
        start_idx = vol_idx * ROOTS_PER_VOLUME
        end_idx = min(start_idx + ROOTS_PER_VOLUME, total_roots)
        vol_roots = roots[start_idx:end_idx]

        temp_html = f"temp_vol_{vol_num:03d}.html"
        final_pdf = f"Language_Reference_Vol_{vol_num:03d}.pdf"

        html = [f"<!DOCTYPE html><html><head><meta charset='UTF-8'><style>{css}</style></head><body>"]
        
        html.append(f"""
        <h1>Language Reference &mdash; Volume {vol_num:03d} (Roots {start_idx + 1} - {end_idx})</h1>
        <div style="border: 2px solid #000; padding: 5px; margin-bottom: 10px; background: #fff;">
            <strong>LEGEND:</strong><br>
            Cells are split into two halves. 
            The <strong>Top White Half [+]</strong> is the Affirmative. 
            The <strong>Bottom Gray Half [-]</strong> is the Negative. 
            English pronunciation is on the left; Arabic script is on the right. 'N/A' means the form is not used.
        </div>
        """)

        for local_idx, root in enumerate(vol_roots):
            r_id = root["id"]
            pb = "page-break" if local_idx > 0 else ""
            
            html.append(f"""
            <div class="{pb}">
                <div class="root-header avoid-break">
                    ROOT ID: {r_id} | SEQUENCE: {root["sub_arabizi"].upper()} 
                    <span class="ar">{root["mother_arabic"]}</span>
                </div>
                <div class="root-meaning avoid-break"><strong>MEANING:</strong> {root["sub_english"]}</div>
                
                <h3>1. Nominals</h3>
                <table class="avoid-break">
                    <tr>
                        <th style="width:26%;">Category</th>
                        <th style="width:37%;">[+] Affirmative</th>
                        <th style="width:37%;">[-] Negative</th>
                    </tr>
            """)

            cursor.execute("SELECT * FROM nominals WHERE root_id = ?", (r_id,))
            nominals = cursor.fetchall()
            n_dict = {}
            for n in nominals:
                cat = n["category"].replace("_", " ").title()
                if cat not in n_dict: n_dict[cat] = {}
                n_dict[cat][n["polarity"]] = n

            for cat, val in n_dict.items():
                explicit_cat = nominals_map.get(cat, cat)
                aff = val.get("affirmative")
                neg = val.get("negative")
                
                def render_nom(data, polarity):
                    if not data: return "<td class='na'>N/A</td>"
                    bg = "aff" if polarity == "+" else "neg"
                    return f"""
                    <td style="padding:0;">
                        <div class="dicho-half {bg}">
                            <span class="sign { 'plus' if polarity=='+' else 'minus' }">{polarity}</span>
                            <span class="en">{data['arabizi']}</span>
                            <span class="ar">{data['arabic']}</span>
                        </div>
                    </td>"""

                html.append(f"<tr><td class='row-header' style='text-align:left; font-size:6.5pt;'>{explicit_cat}</td>")
                html.append(render_nom(aff, "+"))
                html.append(render_nom(neg, "-"))
                html.append("</tr>")
                
            html.append("</table>")

            html.append("<h3>2. Verbs by Region</h3>")
            cursor.execute("SELECT * FROM conjugations WHERE root_id = ?", (r_id,))
            conjs = cursor.fetchall()

            c_map = {}
            for c in conjs:
                d, a, p, pol = c["dialect"], c["aspect"], c["person_id"], c["polarity"]
                if d not in c_map: c_map[d] = {}
                if a not in c_map[d]: c_map[d][a] = {}
                if p not in c_map[d][a]: c_map[d][a][p] = {}
                c_map[d][a][p][pol] = {"ar": c["arabic"], "en": c["arabizi"]}

            for dialect, aspects in c_map.items():
                clean_dialect = dialect.replace('_2_palestine', ' (Palestinian)').replace('_', ' ').title()
                
                html.append(f"""
                <div class="avoid-break" style="margin-bottom: 6px;">
                    <div class="dialect-bar">Dialect: {clean_dialect}</div>
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 14%;">Subject</th>
                """)
                for aspect in aspects_order:
                    html.append(f"<th style='width: 17.2%;'>{aspects_map[aspect]}</th>")
                html.append("</tr></thead><tbody>")

                for p_code, p_name in persons_map.items():
                    html.append(f"<tr><td class='row-header'>{p_name}</td>")
                    
                    for aspect in aspects_order:
                        cell = aspects.get(aspect, {}).get(p_code)
                        if not cell:
                            html.append("<td class='na'>N/A</td>")
                        else:
                            aff = cell.get("affirmative")
                            neg = cell.get("negative")
                            
                            html.append("<td><div class='dicho-cell'>")
                            
                            if aff:
                                html.append(f"""
                                <div class="dicho-half aff">
                                    <span class="sign plus">+</span>
                                    <span class="en">{aff['en']}</span>
                                    <span class="ar">{aff['ar']}</span>
                                </div>""")
                            if neg:
                                html.append(f"""
                                <div class="dicho-half neg">
                                    <span class="sign minus">-</span>
                                    <span class="en">{neg['en']}</span>
                                    <span class="ar">{neg['ar']}</span>
                                </div>""")
                                
                            html.append("</div></td>")
                    html.append("</tr>")
                html.append("</tbody></table></div>")
            html.append("</div>")

        html.append("</body></html>")

        with open(temp_html, "w", encoding="utf-8") as f:
            f.write("\n".join(html))

        print(f"[*] Rendering Volume {vol_num}/{total_volumes} -> {final_pdf}...")
        
        cmd = [
            CHROME_PATH,
            "--headless=old",
            "--disable-gpu",
            "--js-flags=--max-old-space-size=256",
            f"--print-to-pdf={os.path.abspath(final_pdf)}",
            "--no-margins",
            f"file:///{os.path.abspath(temp_html)}"
        ]
        
        subprocess.run(cmd, capture_output=True, text=True)

        if os.path.exists(temp_html):
            os.remove(temp_html)

        if os.path.exists(final_pdf):
            print(f"    [+] Created: {final_pdf} ({os.path.getsize(final_pdf) // 1024} KB)")
        else:
            print(f"    [-] Failed to create {final_pdf}")

    conn.close()
    print("[+] Done.")

if __name__ == "__main__":
    safe_build()