#!/usr/bin/env python3
"""Extract all process sheets with cell-position-based parsing."""
import os, re, sqlite3
from docx import Document
from sizing_engine import infer_process_modes

SRC = os.path.expanduser("~/Desktop/生产工艺单")
DB = os.path.join(os.path.dirname(__file__), "data", "process_sheets.db")

def find_cell(table, label):
    """Find a cell containing `label`, return that cell and its neighbor (value cell)."""
    for row in table.rows:
        cells = row.cells
        for i, cell in enumerate(cells):
            txt = cell.text.strip().replace(' ', '').replace('\n', '')
            if label in txt:
                # Get the value from the next cell (or sometimes same cell)
                if i+1 < len(cells):
                    val = cells[i+1].text.strip()
                    if val and label not in val:
                        return val
    return None

def extract_file(filepath):
    try:
        doc = Document(filepath)
        tables = doc.tables
        if len(tables) < 3:
            return None
        
        data = {
            'file': os.path.basename(filepath),
            'dirname': os.path.basename(os.path.dirname(filepath)),
            'filepath': filepath,
        }
        
        # --- Header ---
        header_text = ' '.join([p.text.strip() for p in doc.paragraphs])
        m = re.search(r'批次号[：:]\s*(\S+)', header_text)
        if m: data['batch_no'] = m.group(1)
        m = re.search(r'下单时间[：:]\s*(\S+)', header_text)
        if m: data['order_date'] = m.group(1)
        
        # --- Table 0: Basic info ---
        t0 = tables[0]
        data['client'] = find_cell(t0, '客户名称')
        data['product'] = find_cell(t0, '产品名称')
        
        qty_str = find_cell(t0, '订单数量')
        if qty_str:
            qty_str = qty_str.replace('只','').strip()
            try: data['order_qty'] = int(float(qty_str))
            except: pass
        
        finished_str = find_cell(t0, '成品数量')
        if finished_str:
            finished_str = finished_str.replace('只','').strip()
            try: data['finished_qty'] = int(float(finished_str))
            except: pass
        
        dims_str = find_cell(t0, '规格')
        if dims_str:
            m = re.search(r'(\d+)\*(\d+)\*(\d+)', dims_str)
            if m:
                data['box_l'], data['box_w'], data['box_h'] = int(m.group(1)), int(m.group(2)), int(m.group(3))
        
        # Notes from last row
        notes_row = t0.rows[-1]
        notes = []
        for cell in notes_row.cells:
            txt = cell.text.strip().replace('\n', ' ')
            if '备注' in txt:
                # Get the actual note content after the colon
                m = re.search(r'备注[：:]\s*(.*)', txt)
                if m and m.group(1):
                    notes.append(m.group(1))
                else:
                    notes.append(txt)
        data['notes'] = '; '.join(set(notes)) if notes else None
        
        # --- Table 1: Paper ---
        t1 = tables[1]
        paper_dim = find_cell(t1, '面纸尺寸')
        if paper_dim:
            m = re.search(r'(\d+)\*(\d+)', paper_dim)
            if m:
                data['paper_w'], data['paper_h'] = int(m.group(1)), int(m.group(2))
        
        data['paper_spec'] = find_cell(t1, '面纸规格型号')
        data['print_qty_str'] = find_cell(t1, '印刷数量')
        
        # Lamination: check which column has 是
        lamination_cells = None
        for row in t1.rows:
            for i, cell in enumerate(row.cells):
                if '覆膜' in cell.text:
                    lamination_cells = row.cells
                    break
            if lamination_cells: break
        
        if lamination_cells:
            # Find which column has '是' under the lamination headers
            lam_text = ' '.join([c.text.strip() for c in lamination_cells])
            if '亮膜' in lam_text and '是' in lam_text.split('亮膜')[1][:3] if '亮膜' in lam_text else False:
                data['lamination'] = '亮膜'
            else:
                data['lamination'] = None
        data['has_lamination'] = 1 if data.get('lamination') else 0
        
        # --- Table 2: Corrugated board ---
        t2 = tables[2]
        board_dim = find_cell(t2, '瓦楞纸板尺寸')
        if board_dim:
            m = re.search(r'(\d+)\*(\d+)', board_dim)
            if m:
                data['board_w'], data['board_h'] = int(m.group(1)), int(m.group(2))
        
        flute = find_cell(t2, '瓦型')
        if flute:
            data['flute_type'] = flute.strip()
        
        material = find_cell(t2, '纸板材质')
        if material:
            data['board_material'] = material.strip()
        
        pad_mat = find_cell(t2, '垫片材质')
        if not pad_mat:
            pad_mat = find_cell(t2, '格档材质')
        if pad_mat:
            data['padding_material'] = pad_mat.strip()
        
        pad_dim = find_cell(t2, '尺寸，mm')
        if pad_dim:
            data['padding_size'] = pad_dim.strip()
        
        # Grid material (格档)
        for row in t2.rows:
            for cell in row.cells:
                if '格档材质' in cell.text:
                    # Get next cell
                    for i, c in enumerate(row.cells):
                        if '格档材质' in c.text and i+1 < len(row.cells):
                            val = row.cells[i+1].text.strip()
                            if val and '格档' not in val:
                                data['grid_material'] = val
        
        # Detect print style from notes
        notes_str = data.get('notes', '') or ''
        if '双拼' in notes_str:
            data['print_style'] = '双拼'
        elif '两页' in notes_str:
            data['print_style'] = '两页成型'
        elif '单页' in notes_str:
            data['print_style'] = '单页成型'
        modes = infer_process_modes(notes_str)
        data['forming_mode'] = modes.forming_mode
        data['face_layout'] = modes.face_layout
        data['board_layout'] = modes.board_layout
        
        data['is_quote'] = '报价' in data.get('file', '') or '报价' in data.get('dirname', '')
        
        return data
    except Exception as e:
        return {'file': os.path.basename(filepath) if filepath else 'unknown', 'error': str(e)}


def main():
    # Drop and recreate
    conn = sqlite3.connect(DB)
    conn.execute('DROP TABLE IF EXISTS process_sheets')
    conn.execute('''
        CREATE TABLE process_sheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file TEXT, dirname TEXT, filepath TEXT,
            batch_no TEXT, order_date TEXT, client TEXT, product TEXT,
            order_qty INTEGER, finished_qty INTEGER,
            box_l INTEGER, box_w INTEGER, box_h INTEGER,
            paper_w INTEGER, paper_h INTEGER, paper_spec TEXT,
            print_qty_str TEXT, lamination TEXT, has_lamination INTEGER DEFAULT 0,
            board_w INTEGER, board_h INTEGER, flute_type TEXT, board_material TEXT,
            padding_material TEXT, padding_size TEXT, grid_material TEXT,
            print_style TEXT, forming_mode TEXT, face_layout TEXT, board_layout TEXT,
            notes TEXT, is_quote INTEGER DEFAULT 0,
            error TEXT
        )
    ''')
    
    total = success = failed = 0
    rows = []
    
    for root, dirs, files in os.walk(SRC):
        for f in files:
            if f.startswith('.') or not f.endswith('.docx'):
                continue
            total += 1
            fp = os.path.join(root, f)
            data = extract_file(fp)
            if data:
                if 'error' in data:
                    failed += 1
                else:
                    success += 1
                rows.append(data)
            
            if total % 500 == 0:
                print(f"Processed {total} files... ({success} ok, {failed} err)")
    
    cols = ['file','dirname','filepath','batch_no','order_date','client','product',
            'order_qty','finished_qty','box_l','box_w','box_h',
            'paper_w','paper_h','paper_spec','print_qty_str','lamination','has_lamination',
            'board_w','board_h','flute_type','board_material',
            'padding_material','padding_size','grid_material',
            'print_style','forming_mode','face_layout','board_layout','notes','is_quote','error']
    
    for r in rows:
        vals = [r.get(c) for c in cols]
        conn.execute(f'INSERT INTO process_sheets ({",".join(cols)}) VALUES ({",".join(["?"]*len(cols))})', vals)
    
    conn.commit()
    
    print(f"\n=== Extraction Complete ===")
    print(f"Total: {total}, Success: {success} ({success*100//max(total,1)}%), Failed: {failed}")
    
    # Quick quality check
    for col, label in [('client','Client'),('order_qty','Qty'),('box_l','Dims'),('paper_spec','Paper'),('flute_type','Flute'),('board_material','Board')]:
        cnt = conn.execute(f"SELECT COUNT(*) FROM process_sheets WHERE error IS NULL AND {col} IS NOT NULL").fetchone()[0]
        print(f"  {label}: {cnt}/{success} ({cnt*100//max(success,1)}%)")
    
    # Distribution
    print("\nClient distribution:")
    for row in conn.execute("SELECT client, COUNT(*) FROM process_sheets WHERE client IS NOT NULL GROUP BY client ORDER BY COUNT(*) DESC LIMIT 12").fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    print("\nFlute distribution:")
    for row in conn.execute("SELECT flute_type, COUNT(*) FROM process_sheets WHERE flute_type IS NOT NULL GROUP BY flute_type ORDER BY COUNT(*) DESC").fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    conn.close()
    print(f"\nDB: {DB}")

if __name__ == '__main__':
    main()
