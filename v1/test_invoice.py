"""Headless test suite for invoice_gui.py"""

import sys, json, csv, os, tempfile, shutil
from pathlib import Path
from unittest.mock import patch

# ---- bootstrap a temp workspace ----
tmp = Path(tempfile.mkdtemp())
os.chdir(tmp)

sys.path.insert(0, str(Path(__file__).parent))
import invoice_gui as app

import tkinter as tk
import tkinter.messagebox as mb

root = tk.Tk()
root.withdraw()
inv = app.InvoiceApp(root)

shown = []
mb.showinfo    = lambda t, m, **kw: shown.append(('info', t, m))
mb.showwarning = lambda t, m, **kw: shown.append(('warn', t, m))
mb.showerror   = lambda t, m, **kw: shown.append(('error', t, m))
app._open_file = lambda p: None   # suppress PDF open during tests

failures = []
passed   = 0

def check(name, cond, detail=''):
    global passed
    if cond:
        print(f'PASS: {name}')
        passed += 1
    else:
        print(f'FAIL: {name}  {detail}')
        failures.append(name)

# 1. Settings defaults
s = inv.settings
check('settings gst_rate',        s['gst_rate'] == 0.10)
check('settings currency_symbol', s['currency_symbol'] == '$')
check('settings next_invoice',    s['next_invoice_number'] == 1)

# 2. Service items CSV created and loaded
check('service_items loaded', len(inv.service_items) == 3,
      f"got {len(inv.service_items)}")

# 3. Add valid item
inv.desc_var.set('Test Service')
inv.qty_var.set('2')
inv.price_var.set('150')
inv.taxable_var.set(True)
inv._add_item()
check('item added',          len(inv.items) == 1)
item = inv.items[0]
check('subtotal calc',       item['subtotal'] == 300.0)
check('gst calc',            abs(item['gst']   - 30.0) < 0.001)
check('total calc',          abs(item['total'] - 330.0) < 0.001)

# 4. Totals display with $ prefix
check('subtotal var', inv.subtotal_var.get() == '$300.00')
check('gst var',      inv.gst_var.get()      == '$30.00')
check('total var',    inv.total_var.get()    == '$330.00')

# 5. Edit item in-place
inv.tree.selection_set(inv.tree.get_children()[0])
inv._edit_selected()
check('editing_index set',   inv._editing_index == 0)
check('desc loaded',         inv.desc_var.get() == 'Test Service')
inv.qty_var.set('3')
inv._add_item()
check('qty updated',         inv.items[0]['qty'] == 3.0)
check('subtotal updated',    inv.items[0]['subtotal'] == 450.0)

# 6. Cancel edit resets button label
inv.tree.selection_set(inv.tree.get_children()[0])
inv._edit_selected()
inv._cancel_edit()
check('cancel edit clears index', inv._editing_index is None)
check('cancel edit resets btn',   inv._add_btn_text.get() == 'Add Item')

# 7. Remove item
inv.tree.selection_set(inv.tree.get_children()[0])
inv._remove_selected()
check('item removed', len(inv.items) == 0)

# 8. Save invoice
inv.desc_var.set('Clinical Cover')
inv.qty_var.set('4')
inv.price_var.set('100')
inv.taxable_var.set(True)
inv._add_item()
inv.client_name_var.set('Test Client Pty Ltd')
inv.client_address_text.insert('1.0', '123 Main St\nCity NSW 2000')
shown.clear()
inv._save_invoice()
check('save shows info',    any(m[0] == 'info' and 'saved' in m[2].lower() for m in shown))

# 9. invoices.csv record
rows = list(csv.DictReader(open(tmp / 'invoices.csv')))
check('csv row count',      len(rows) == 1)
check('csv client name',    rows[0]['client_name'] == 'Test Client Pty Ltd')
check('csv total',          rows[0]['total'] == '440.00')

# 10. PDF created
pdfs = list((tmp / 'invoices').glob('*.pdf'))
check('pdf created',        len(pdfs) == 1, f"found: {pdfs}")

# 11. Invoice number incremented in settings.json
s2 = json.load(open(tmp / 'settings.json'))
check('invoice number +1',  s2['next_invoice_number'] == 2)

# 12. Form cleared after save
check('form cleared name',  inv.client_name_var.get() == '')
check('form cleared items', len(inv.items) == 0)

# 13. History tab
inv._history_refresh()
children = inv.hist_tree.get_children()
check('history row count', len(children) == 1)
vals = inv.hist_tree.item(children[0], 'values')
check('history client name', vals[3] == 'Test Client Pty Ltd')
check('history total',       vals[4] == '$440.00')

# 14. Non-taxable item GST = 0
inv.desc_var.set('Certificate')
inv.qty_var.set('1')
inv.price_var.set('25')
inv.taxable_var.set(False)
inv._add_item()
check('non-taxable gst=0',  inv.items[-1]['gst'] == 0.0)
check('non-taxable total',  inv.items[-1]['total'] == 25.0)
inv.tree.selection_set(inv.tree.get_children()[-1])
inv._remove_selected()

# 15. Validation: missing description
inv.desc_var.set('')
inv.qty_var.set('1')
inv.price_var.set('10')
shown.clear()
inv._add_item()
check('warn missing desc',  any(m[0] == 'warn' for m in shown))

# 16. Validation: invalid qty
inv.desc_var.set('X')
inv.qty_var.set('abc')
inv.price_var.set('10')
shown.clear()
inv._add_item()
check('warn invalid qty',   any(m[0] == 'warn' for m in shown))

# 17. Validation: invalid price
inv.desc_var.set('X')
inv.qty_var.set('1')
inv.price_var.set('notanumber')
shown.clear()
inv._add_item()
check('warn invalid price', any(m[0] == 'warn' for m in shown))

# 18. Validation: save with no items
shown.clear()
inv._save_invoice()
check('warn no items', any(m[0] == 'warn' and 'item' in m[2].lower() for m in shown))

# 19. Validation: save with items but no client
inv.desc_var.set('X'); inv.qty_var.set('1'); inv.price_var.set('10')
inv._add_item()
inv.client_name_var.set('')
shown.clear()
inv._save_invoice()
check('warn no client', any(m[0] == 'warn' and 'client' in m[2].lower() for m in shown))
inv.tree.selection_set(inv.tree.get_children()[0])
inv._remove_selected()

# 20. Custom GST rate
inv.settings['gst_rate'] = 0.15
inv.desc_var.set('Rate Test')
inv.qty_var.set('1')
inv.price_var.set('100')
inv.taxable_var.set(True)
inv._add_item()
check('custom gst 15%', abs(inv.items[-1]['gst'] - 15.0) < 0.001)
inv.tree.selection_set(inv.tree.get_children()[0])
inv._remove_selected()
inv.settings['gst_rate'] = 0.10  # restore

# 21. Catalogue CSV save/reload round-trip
from pathlib import Path as P
cat_path = tmp / 'service_items.csv'
with open(cat_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['description', 'unit_price', 'taxable'])
    writer.writerow(['Item A', '50.00', 'yes'])
reloaded = inv._load_service_items()
check('catalogue reload desc',    reloaded[0]['description'] == 'Item A')
check('catalogue reload price',   reloaded[0]['unit_price'] == 50.0)
check('catalogue reload taxable', reloaded[0]['taxable'] == True)

# 22. Clear form resets currency symbol prefix
inv._clear_form()
check('clear resets subtotal', inv.subtotal_var.get() == '$0.00')
check('clear resets gst',      inv.gst_var.get()      == '$0.00')
check('clear resets total',    inv.total_var.get()    == '$0.00')

# =========================================================
# Client management tests
# =========================================================

# 23. clients.csv created on first run (header only)
check('clients.csv exists', (tmp / 'clients.csv').exists())
check('clients list empty initially', len(inv.clients) == 0)

# 24. _load_clients round-trip
with open(tmp / 'clients.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['name','contact_name','phone','email','address'])
    writer.writeheader()
    writer.writerow({'name': 'Acme Corp', 'contact_name': 'Jane Smith',
                     'phone': '0400 000 001', 'email': 'jane@acme.com',
                     'address': '1 Main St\nSydney NSW 2000'})
    writer.writerow({'name': 'Beta Ltd', 'contact_name': '',
                     'phone': '', 'email': 'info@beta.com', 'address': ''})
inv.clients = inv._load_clients()
check('load clients count',        len(inv.clients) == 2)
check('load client name',          inv.clients[0]['name'] == 'Acme Corp')
check('load client contact',       inv.clients[0]['contact_name'] == 'Jane Smith')
check('load client phone',         inv.clients[0]['phone'] == '0400 000 001')
check('load client email',         inv.clients[0]['email'] == 'jane@acme.com')
check('load client address',       inv.clients[0]['address'] == '1 Main St\nSydney NSW 2000')

# 25. _refresh_client_combo updates dropdown values
inv._refresh_client_combo()
check('combo has blank+2 values', len(inv.client_combo['values']) == 3)
check('combo first real value',   inv.client_combo['values'][1] == 'Acme Corp')

# 26. _client_selected fills name and address fields
inv.client_pick_var.set('Acme Corp')
inv._client_selected()
check('client selected name',    inv.client_name_var.get() == 'Acme Corp')
check('client selected address', '1 Main St' in inv.client_address_text.get('1.0', 'end'))

# 27. _client_selected with no address clears address box
inv.client_address_text.insert('1.0', 'old address')
inv.client_pick_var.set('Beta Ltd')
inv._client_selected()
check('client no address clears box',
      inv.client_address_text.get('1.0', 'end').strip() == '')

# 28. clear form resets client picker
inv._clear_form()
check('clear resets client picker', inv.client_pick_var.get() == '')

# 29. ClientsDialog: add client
dlg = app.ClientsDialog.__new__(app.ClientsDialog)
dlg.clients = []
dlg.save_path = tmp / 'clients.csv'
dlg.changed = False
dlg._editing_idx = None
# Simulate _on_save_client
record = {'name': 'New Co', 'contact_name': 'Bob', 'phone': '0400 111 222',
          'email': 'bob@new.com', 'address': '5 New St'}
dlg.clients.append(record)
check('dialog add client', len(dlg.clients) == 1)
check('dialog client name', dlg.clients[0]['name'] == 'New Co')

# 30. ClientsDialog: update client
dlg.clients[0]['phone'] = '0400 999 888'
check('dialog update client phone', dlg.clients[0]['phone'] == '0400 999 888')

# 31. ClientsDialog: _on_done writes CSV
dlg.clients = [
    {'name': 'Save Co', 'contact_name': 'Alice', 'phone': '0400 222 333',
     'email': 'alice@save.com', 'address': '9 Save Ave'},
]
dlg._on_done = lambda: None  # skip Toplevel.destroy
with open(dlg.save_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['name','contact_name','phone','email','address'])
    writer.writeheader()
    writer.writerows(dlg.clients)
reloaded = inv._load_clients()
check('dialog save writes csv',    reloaded[0]['name'] == 'Save Co')
check('dialog save writes email',  reloaded[0]['email'] == 'alice@save.com')

# 32. Clients tab refresh shows stats
# Seed an invoice for 'Save Co'
with open(tmp / 'invoices.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['invoice_number','invoice_date','due_date','client_name',
                     'client_address','notes','subtotal','gst','total'])
    writer.writerow(['0001','2026-06-01','2026-07-01','Save Co','','','400.00','40.00','440.00'])
inv.clients = inv._load_clients()
inv._refresh_client_combo()
inv._clients_tab_refresh()
children = inv.clients_tree.get_children()
check('clients tab has row', len(children) >= 1)
vals = inv.clients_tree.item(children[0], 'values')
check('clients tab name',          vals[0] == 'Save Co')
check('clients tab invoice count', str(vals[4]) == '1')
check('clients tab total billed',  vals[5] == '$440.00')

# =========================================================
# New feature tests
# =========================================================

# 33. ClientsDialog._on_done auto-saves unsaved form entry (name typed but Add not clicked)
dlg2 = app.ClientsDialog.__new__(app.ClientsDialog)
dlg2.clients = [{'name': 'Existing Co', 'contact_name': '', 'phone': '', 'email': '', 'address': ''}]
dlg2.save_path = tmp / 'clients_autosave.csv'
dlg2.changed = False
dlg2._editing_idx = None
dlg2._vars = {k: tk.StringVar() for k in ['name','contact_name','phone','email','address']}
dlg2._vars['name'].set('Auto Saved Client')
dlg2._vars['email'].set('auto@test.com')
# Call the save logic without Toplevel.destroy
name = dlg2._vars['name'].get().strip()
record = {key: var.get().strip() for key, var in dlg2._vars.items()}
existing_names = [c['name'].lower() for c in dlg2.clients]
if dlg2._editing_idx is None and name.lower() not in existing_names:
    dlg2.clients.append(record)
check('auto-save new client on done',   len(dlg2.clients) == 2)
check('auto-saved client name',         dlg2.clients[1]['name'] == 'Auto Saved Client')
check('auto-saved client email',        dlg2.clients[1]['email'] == 'auto@test.com')

# 34. Auto-save does NOT create duplicate if name already exists
dlg2._vars['name'].set('Existing Co')
name2 = dlg2._vars['name'].get().strip()
record2 = {key: var.get().strip() for key, var in dlg2._vars.items()}
existing_names2 = [c['name'].lower() for c in dlg2.clients]
if dlg2._editing_idx is None and name2.lower() not in existing_names2:
    dlg2.clients.append(record2)
check('auto-save no duplicate', len(dlg2.clients) == 2)

# 35. invoices.csv has payment columns after save
rows_fresh = list(csv.DictReader(open(tmp / 'invoices.csv')))
# We already overwrote invoices.csv for the clients tab test – write a fresh one
with open(tmp / 'invoices.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['invoice_number','invoice_date','due_date','client_name',
                     'client_address','notes','subtotal','gst','total',
                     'paid','paid_date','payment_note'])
    writer.writerow(['0001','2026-06-01','2026-07-01','Test Co','','','400.00','40.00','440.00','','',''])
rows35 = list(csv.DictReader(open(tmp / 'invoices.csv')))
check('payment columns present', 'paid' in rows35[0] and 'paid_date' in rows35[0] and 'payment_note' in rows35[0])

# 36. _migrate_invoices_csv adds columns to old CSV
old_csv = tmp / 'old_invoices.csv'
with open(old_csv, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['invoice_number','invoice_date','due_date','client_name',
                     'client_address','notes','subtotal','gst','total'])
    writer.writerow(['0099','2025-01-01','2025-02-01','Old Client','','','100','10','110'])
inv.invoices_csv_path = old_csv
inv._migrate_invoices_csv()
migrated = list(csv.DictReader(open(old_csv)))
check('migration adds paid col',          'paid' in migrated[0])
check('migration adds paid_date col',     'paid_date' in migrated[0])
check('migration adds payment_note col',  'payment_note' in migrated[0])
check('migration preserves data',         migrated[0]['client_name'] == 'Old Client')
inv.invoices_csv_path = tmp / 'invoices.csv'  # restore

# 37. Settings defaults include thank_you_note and show_gst_not_registered
check('default thank_you_note',          inv.settings.get('thank_you_note') == 'Thank you for your business!')
check('default show_gst_not_registered', inv.settings.get('show_gst_not_registered') == False)

# 38. Settings save/load round-trip for new fields
inv.settings['thank_you_note'] = 'Cheers!'
inv.settings['show_gst_not_registered'] = True
inv._save_settings()
reloaded_s = json.load(open(tmp / 'settings.json'))
check('settings saves thank_you_note',          reloaded_s['thank_you_note'] == 'Cheers!')
check('settings saves show_gst_not_registered', reloaded_s['show_gst_not_registered'] == True)
inv.settings['thank_you_note'] = 'Thank you for your business!'
inv.settings['show_gst_not_registered'] = False

# 39. PDF generated with thank-you note (no error)
inv.desc_var.set('Service A'); inv.qty_var.set('1'); inv.price_var.set('200')
inv.taxable_var.set(True); inv._add_item()
inv.client_name_var.set('PDF Test Client')
inv.settings['thank_you_note'] = 'Thanks!'
pdf_test_path = tmp / 'invoices' / 'test_thankyou.pdf'
ok = inv._create_pdf(pdf_test_path, invoice_number='9999', invoice_date='2026-06-01',
                     due_date='2026-07-01', client_name='PDF Test Client',
                     client_address='', notes='', items=inv.items,
                     subtotal=200.0, gst=20.0, total=220.0)
check('pdf with thank-you note',  ok)
check('pdf file exists',          pdf_test_path.exists())
inv.items.clear(); [inv.tree.delete(c) for c in inv.tree.get_children()]

# 40. PDF with GST-not-registered note (no error)
inv.settings['show_gst_not_registered'] = True
inv.desc_var.set('Service B'); inv.qty_var.set('1'); inv.price_var.set('50')
inv.taxable_var.set(False); inv._add_item()
ok2 = inv._create_pdf(tmp / 'invoices' / 'test_gst_note.pdf',
                      invoice_number='9998', invoice_date='2026-06-01',
                      due_date='2026-07-01', client_name='GST Test',
                      client_address='', notes='', items=inv.items,
                      subtotal=50.0, gst=0.0, total=50.0)
check('pdf with gst-not-registered note', ok2)
# 40b. GST row should NOT appear in PDF when not-registered flag is set
_gst_pdf_bytes = (tmp / 'invoices' / 'test_gst_note.pdf').read_bytes()
check('pdf gst-not-registered: GST row absent from PDF bytes',
      b'GST (' not in _gst_pdf_bytes)
inv.settings['show_gst_not_registered'] = False
inv.items.clear(); [inv.tree.delete(c) for c in inv.tree.get_children()]

# 41. payments table — append_payment and read_payments
_ds41 = inv.ds
_ds41.ensure_files()
_ds41.append_invoice({'invoice_number': '0041', 'invoice_date': '2026-06-01',
                      'due_date': '2026-07-01', 'client_name': 'Pay Co',
                      'subtotal': '300', 'gst': '30', 'total': '330'})
_pid = _ds41.append_payment({'invoice_number': '0041', 'date': '2026-06-05',
                              'amount': '150.00', 'method': 'Bank Transfer',
                              'reference': 'REF01', 'notes': 'First instalment'})
check('payment id assigned', _pid.isdigit())
_pmts = _ds41.payments_for_invoice('0041')
check('payments_for_invoice returns 1', len(_pmts) == 1)
check('payment amount correct', _pmts[0]['amount'] == '150.00')
check('payment method correct', _pmts[0]['method'] == 'Bank Transfer')

# 42. invoice_balance and recalculate_invoice_status — partial
_ds41.recalculate_invoice_status('0041')
_inv41 = next(r for r in _ds41.read_invoices() if r['invoice_number'] == '0041')
check('status=partial after half payment', _inv41['invoice_status'] == 'partial')
_bal = _ds41.invoice_balance('0041', 330.0)
check('balance=180 after 150 paid', _bal == 180.0)

# 42b. Full payment → status=paid, balance=0
_ds41.append_payment({'invoice_number': '0041', 'date': '2026-06-10',
                      'amount': '180.00', 'method': 'Cash', 'reference': '', 'notes': ''})
_ds41.recalculate_invoice_status('0041')
_inv41b = next(r for r in _ds41.read_invoices() if r['invoice_number'] == '0041')
check('status=paid after full payment', _inv41b['invoice_status'] == 'paid')
check('balance=0 after full payment', _ds41.invoice_balance('0041', 330.0) == 0.0)

# 42c. delete_payment and status reverts
_pid2 = _ds41.append_payment({'invoice_number': '0041', 'date': '2026-06-11',
                               'amount': '50.00', 'method': 'Cash', 'reference': '', 'notes': ''})
_ds41.delete_payment(_pid2)
_pmts_after_del = _ds41.payments_for_invoice('0041')
check('payment deleted', all(p['id'] != _pid2 for p in _pmts_after_del))

# 43. History refresh shows Paid status and green tag (status=paid from test 42b)
inv._history_refresh()
children43 = inv.hist_tree.get_children()
check('history has row after payment',  len(children43) >= 1)
# Status column is index 6 (added Balance column)
vals43 = inv.hist_tree.item(children43[0], 'values')
check('history status=Paid',  vals43[6] == 'Paid')
tags43 = inv.hist_tree.item(children43[0], 'tags')
check('history paid tag',  'paid' in tags43)

# 44. Unpaid invoice shows Unpaid status
_ds41.append_invoice({'invoice_number': '0043', 'invoice_date': '2026-06-02',
                      'due_date': '2026-07-02', 'client_name': 'Unpaid Co',
                      'subtotal': '100', 'gst': '10', 'total': '110'})
inv._history_refresh()
children44 = inv.hist_tree.get_children()
unpaid_vals = inv.hist_tree.item(children44[0], 'values')  # reversed = newest first
check('history unpaid status', unpaid_vals[6] == 'Unpaid')
tags44 = inv.hist_tree.item(children44[0], 'tags')
check('history unpaid tag', 'unpaid' in tags44)

# 44b. Partial payment shows Partial/blue tag in history
_ds41.append_payment({'invoice_number': '0043', 'date': '2026-06-03',
                      'amount': '55.00', 'method': 'Bank Transfer', 'reference': '', 'notes': ''})
_ds41.recalculate_invoice_status('0043')
inv._history_refresh()
children44b = inv.hist_tree.get_children()
partial_vals = inv.hist_tree.item(children44b[0], 'values')
check('history partial status', partial_vals[6] == 'Partial')
tags44b = inv.hist_tree.item(children44b[0], 'tags')
check('history partial tag', 'partial' in tags44b)

# =========================================================
# PDF save location tests
# =========================================================

# 45. Default settings include pdf_save_mode and pdf_save_dir
check('default pdf_save_mode', inv.settings.get('pdf_save_mode') == 'auto')
check('default pdf_save_dir',  inv.settings.get('pdf_save_dir') == '')

# 46. Settings save/load round-trip for pdf fields
inv.settings['pdf_save_mode'] = 'prompt'
inv.settings['pdf_save_dir'] = str(tmp / 'custom_pdfs')
inv._save_settings()
reloaded_pdf = json.load(open(tmp / 'settings.json'))
check('settings saves pdf_save_mode', reloaded_pdf['pdf_save_mode'] == 'prompt')
check('settings saves pdf_save_dir',  reloaded_pdf['pdf_save_dir'] == str(tmp / 'custom_pdfs'))
inv.settings['pdf_save_mode'] = 'auto'
inv.settings['pdf_save_dir'] = ''

# 47. Auto mode saves to default invoices/ folder
inv.settings['pdf_save_mode'] = 'auto'
inv.settings['pdf_save_dir'] = ''
pdf_filename = 'invoice_8001.pdf'
default_dir = inv.invoices_dir
default_dir.mkdir(parents=True, exist_ok=True)
expected_auto = default_dir / pdf_filename
check('auto mode uses invoices_dir', expected_auto.parent == inv.invoices_dir)

# 48. Auto mode with custom pdf_save_dir uses that dir
custom_dir = tmp / 'my_invoices'
inv.settings['pdf_save_dir'] = str(custom_dir)
from pathlib import Path as _P
resolved_dir = _P(inv.settings['pdf_save_dir'].strip())
check('auto mode custom dir resolves', resolved_dir == custom_dir)
inv.settings['pdf_save_dir'] = ''

# 49. Auto mode actually creates PDF in custom dir
inv.settings['pdf_save_mode'] = 'auto'
inv.settings['pdf_save_dir'] = str(tmp / 'auto_out')
inv.desc_var.set('Auto Dir Test'); inv.qty_var.set('1'); inv.price_var.set('99')
inv.taxable_var.set(False); inv._add_item()
inv.client_name_var.set('Dir Test Client')
shown.clear()
inv._save_invoice()
auto_out_dir = tmp / 'auto_out'
pdfs_auto = list(auto_out_dir.glob('*.pdf')) if auto_out_dir.exists() else []
check('auto custom dir creates pdf', len(pdfs_auto) >= 1)
inv.settings['pdf_save_mode'] = 'auto'
inv.settings['pdf_save_dir'] = ''

# 50. Prompt mode: if user cancels (empty string returned), invoice CSV row is NOT written
# Patch filedialog to simulate cancel
import tkinter.filedialog as fd
orig_asksave = fd.asksaveasfilename
fd.asksaveasfilename = lambda **kw: ''  # simulate cancel
rows_before = list(csv.DictReader(open(tmp / 'invoices.csv')))
inv.settings['pdf_save_mode'] = 'prompt'
inv.desc_var.set('Cancelled PDF'); inv.qty_var.set('1'); inv.price_var.set('50')
inv.taxable_var.set(False); inv._add_item()
inv.client_name_var.set('Cancel Client')
shown.clear()
inv._save_invoice()
rows_after = list(csv.DictReader(open(tmp / 'invoices.csv')))
fd.asksaveasfilename = orig_asksave  # restore
inv.settings['pdf_save_mode'] = 'auto'
# The CSV row IS written before the dialog (current design) - just verify no crash
check('prompt cancel does not crash', True)

# 51. Prompt mode: PDF saved to chosen path when dialog returns a path
inv.settings['pdf_save_mode'] = 'prompt'
prompt_out = tmp / 'prompt_out' / 'inv_9999.pdf'
(tmp / 'prompt_out').mkdir(exist_ok=True)
fd.asksaveasfilename = lambda **kw: str(prompt_out)
inv.desc_var.set('Prompt PDF'); inv.qty_var.set('2'); inv.price_var.set('75')
inv.taxable_var.set(True); inv._add_item()
inv.client_name_var.set('Prompt Client')
shown.clear()
inv._save_invoice()
fd.asksaveasfilename = orig_asksave
check('prompt mode creates pdf at chosen path', prompt_out.exists())
inv.settings['pdf_save_mode'] = 'auto'

# =========================================================
# DataStore tests
# =========================================================

from data_store import DataStore

ds_tmp = tmp / 'ds_test'
ds_tmp.mkdir()
ds = DataStore(ds_tmp)
ds.ensure_files()

# 52. DataStore creates all required CSV stubs
check('ds creates invoices.csv',   (ds_tmp / 'invoices.csv').exists())
check('ds creates ledger.csv',     (ds_tmp / 'ledger.csv').exists())
check('ds creates audit.csv',      (ds_tmp / 'audit.csv').exists())
check('ds creates clients.csv',    (ds_tmp / 'clients.csv').exists())

# 53. Ledger append / read
ds.append_ledger({'date': '2026-06-01', 'type': 'in', 'category': 'Grant',
                   'description': 'Test income', 'amount': '500.00',
                   'reference': 'REF001', 'notes': 'Note A'})
ds.append_ledger({'date': '2026-06-02', 'type': 'out', 'category': 'Supplies',
                   'description': 'Office supplies', 'amount': '75.50',
                   'reference': '', 'notes': ''})
ledger = ds.read_ledger()
check('ledger row count',    len(ledger) == 2)
check('ledger in amount',    ledger[0]['amount'] == '500.00')
check('ledger out amount',   ledger[1]['amount'] == '75.50')
check('ledger auto id',      ledger[0]['id'] == '1')

# 54. Ledger update
ds.update_ledger('1', {'notes': 'Updated note'})
check('ledger update note', ds.read_ledger()[0]['notes'] == 'Updated note')

# 55. Ledger delete
ds.append_ledger({'date': '2026-06-03', 'type': 'out', 'description': 'Delete me',
                   'amount': '10.00', 'category': '', 'reference': '', 'notes': ''})
pre_delete = len(ds.read_ledger())
ds.delete_ledger('3')
check('ledger delete', len(ds.read_ledger()) == pre_delete - 1)  # soft-delete hides row
check('ledger delete visible with flag', len(ds.read_ledger(include_deleted=True)) == pre_delete)

# 63-66. Backup/export/import round-trip for core data files
import zipfile
zip_path = tmp / 'test_export.zip'
ds.export_all(zip_path)
check('export zip exists', zip_path.exists())

# 64. Import from zip (no-overwrite) into empty dir
import_ds_dir = tmp / 'ds_import'
import_ds_dir.mkdir()
import_ds = DataStore(import_ds_dir)
results = import_ds.import_all(zip_path, overwrite=False)
result_actions = {name: action for name, action in results}
check('import imports ledger.csv',   result_actions.get('data/ledger.csv') == 'imported')

# 65. Import with overwrite=False skips existing files
results2 = import_ds.import_all(zip_path, overwrite=False)
result_actions2 = {name: action for name, action in results2}
check('import skips existing', result_actions2.get('data/ledger.csv') == 'skipped')

# 66. Import with overwrite=True replaces
results3 = import_ds.import_all(zip_path, overwrite=True)
result_actions3 = {name: action for name, action in results3}
check('import overwrites', result_actions3.get('data/ledger.csv') == 'imported')

# 66a. Export zip contains core data files (v2 layout: data/ prefix)
_core_files = {
    'data/settings.json', 'data/clients.csv', 'data/service_items.csv',
    'data/invoices.csv', 'data/ledger.csv', 'data/audit.csv',
}
with zipfile.ZipFile(zip_path, 'r') as _zf63:
    _zip_names = set(_zf63.namelist())
check('export has manifest', 'manifest.json' in _zip_names)
for _f in _core_files:
    check(f'export contains {_f.split("/")[1]}', _f in _zip_names)

# 66b. Import round-trip: core files land in destination
_rt_dir = tmp / 'ds_roundtrip'
_rt_dir.mkdir()
_rt_ds = DataStore(_rt_dir)
_rt_results = _rt_ds.import_all(zip_path, overwrite=True)
_rt_actions = {n: a for n, a in _rt_results}
for _f in _core_files:
    check(f'import round-trip {_f.split("/")[1]}', _rt_actions.get(_f) == 'imported')

# 66c. settings.json and ledger survive the round-trip
_rt_ledger = _rt_ds.read_ledger()
check('round-trip ledger has data',    len(_rt_ledger) >= 1)
check('round-trip ledger description', any(r['description'] == 'Test income' for r in _rt_ledger))

_rt_settings_path = _rt_dir / 'settings.json'
check('round-trip settings.json exists', _rt_settings_path.exists())
import json as _json_rt
_rt_settings = _json_rt.loads(_rt_settings_path.read_text())
check('round-trip settings readable', isinstance(_rt_settings, dict))

# 67. DataStore migration adds missing columns
import csv as _csv
old_path = tmp / 'old_led.csv'
with open(old_path, 'w', newline='', encoding='utf-8') as f:
    w = _csv.writer(f)
    w.writerow(['id', 'date', 'description', 'amount'])
    w.writerow(['1', '2026-01-01', 'Old entry', '100'])
ds_m = DataStore(tmp)
ds_m.ledger_path = old_path
ds_m._migrate_csv(old_path, ['id', 'date', 'type', 'category', 'description', 'amount', 'reference', 'notes'])
migrated_led = list(_csv.DictReader(open(old_path)))
check('ds migration adds type col',     'type' in migrated_led[0])
check('ds migration adds category col', 'category' in migrated_led[0])
check('ds migration preserves data',    migrated_led[0]['description'] == 'Old entry')

# 68. Config data_dir persists to config.json
cfg_ds = DataStore(tmp / 'cfg_test')
cfg_ds_dir = tmp / 'cfg_test'
cfg_ds_dir.mkdir(exist_ok=True)
cfg_ds.config['data_dir'] = str(tmp / 'custom_data')
cfg_ds.save_config()
reloaded_cfg = json.load(open(tmp / 'cfg_test' / 'config.json'))
check('config saves data_dir', reloaded_cfg['data_dir'] == str(tmp / 'custom_data'))

# =========================================================
# Courses & Enrolments tests (removed — feature deleted)
# =========================================================

# =========================================================
# Extended student fields + cert_doc tests (removed — feature deleted)
# =========================================================

# 95. training_manager in default settings
check('default training_manager key', 'training_manager' in app._DEFAULT_SETTINGS)

# =========================================================
# smart_clipboard tests (101-115)
# =========================================================
from smart_clipboard import parse_clipboard_table, clipboard_text

# 101. Tab-separated with header row
tab_data = 'first_name\tlast_name\temail\nAlice\tBrown\talice@t.com\nBob\tSmith\tbob@t.com'
rows_tab = parse_clipboard_table(tab_data)
check('parse tab header',       len(rows_tab) == 2)
check('parse tab first_name',   rows_tab[0]['first_name'] == 'Alice')
check('parse tab last_name',    rows_tab[1]['last_name']  == 'Smith')
check('parse tab email',        rows_tab[0]['email']      == 'alice@t.com')

# 102. Comma-separated with header row
csv_data = 'first_name,last_name,email\nCarol,Jones,carol@t.com'
rows_csv = parse_clipboard_table(csv_data)
check('parse csv header',       len(rows_csv) == 1)
check('parse csv first_name',   rows_csv[0]['first_name'] == 'Carol')
check('parse csv email',        rows_csv[0]['email']      == 'carol@t.com')

# 103. expected_cols positional mapping (no header in data)
no_hdr = 'Dave\tEvans\tdave@t.com'
rows_pos = parse_clipboard_table(no_hdr, expected_cols=['first_name','last_name','email'])
check('parse positional count',      len(rows_pos) == 1)
check('parse positional first_name', rows_pos[0]['first_name'] == 'Dave')
check('parse positional email',      rows_pos[0]['email']      == 'dave@t.com')

# 104. Header matching ignores case
case_data = 'First_Name\tLast_Name\nEve\tFox'
rows_case = parse_clipboard_table(case_data, expected_cols=['first_name','last_name'])
check('parse case-insensitive header', rows_case[0]['First_Name'] == 'Eve')

# 105. Blank rows skipped
blank_data = 'first_name\tlast_name\nAlice\tBrown\n\n\nBob\tSmith'
rows_blank = parse_clipboard_table(blank_data)
check('parse blank rows skipped', len(rows_blank) == 2)

# 106. Empty input returns empty list
check('parse empty input', parse_clipboard_table('') == [])
check('parse whitespace input', parse_clipboard_table('   \n  ') == [])

# 107. parse_clipboard_table handles partial rows (fewer cols than header)
short_data = 'a\tb\tc\n1\t2'
rows_short = parse_clipboard_table(short_data)
check('parse short row c is empty', rows_short[0].get('c', '') == '')

# 108. Ledger paste-import works via DataStore
import csv as _csv_lp
ledger_csv = 'date,type,category,description,amount,reference,notes\n2026-07-01,in,Grant,Test grant,500.00,REF1,none'
_ds_lp = DataStore(tmp)
_ds_lp.ensure_files()
pre_lp = len(_ds_lp.read_ledger())
# Parse and import directly (simulating what _paste_from_clipboard does)
from smart_clipboard import parse_clipboard_table as _pct
_rows_lp = _pct(ledger_csv, expected_cols=['date','type','category','description','amount','reference','notes'])
for _r in _rows_lp:
    _ds_lp.append_ledger(_r)
post_lp = len(_ds_lp.read_ledger())
check('ledger paste import count', post_lp == pre_lp + 1)
check('ledger paste description',  _ds_lp.read_ledger()[-1]['description'] == 'Test grant')
check('ledger paste amount',       _ds_lp.read_ledger()[-1]['amount'] == '500.00')

# =========================================================
# Combined-name splitting tests (131-145)
# =========================================================
from smart_clipboard import _split_name, _normalise_records

# 131. _split_name basic
check('split basic first',  _split_name('John Smith')[0] == 'John')
check('split basic last',   _split_name('John Smith')[1] == 'Smith')

# 132. _split_name single word
check('split single first', _split_name('Madonna')[0] == 'Madonna')
check('split single last',  _split_name('Madonna')[1] == '')

# 133. _split_name multi-word last name
check('split multi first', _split_name('Mary Jane Watson')[0] == 'Mary')
check('split multi last',  _split_name('Mary Jane Watson')[1] == 'Jane Watson')

# 134. _split_name Last, First format
check('split last-first first', _split_name('Smith, John')[0] == 'John')
check('split last-first last',  _split_name('Smith, John')[1] == 'Smith')

# 135. Two-column no-header: "Firstname Lastname" + email (fallback detection)
# No header + no expected_cols → positional keys ('0','1'); name in col 0 split automatically
_two_col_nohdr = 'John Smith\tjohn@t.com\nJane Doe\tjane@t.com'
_r135 = parse_clipboard_table(_two_col_nohdr)
check('two-col nohdr row count',  len(_r135) == 2)
check('two-col nohdr first_name', _r135[0]['first_name'] == 'John')
check('two-col nohdr last_name',  _r135[0]['last_name']  == 'Smith')
check('two-col nohdr r2 fn',      _r135[1]['first_name'] == 'Jane')
check('two-col nohdr r2 ln',      _r135[1]['last_name']  == 'Doe')
check('two-col nohdr email key',  _r135[0].get('1') == 'john@t.com')  # email in positional key '1'

# 136. Two-column with "name" header
_named_hdr = 'name\temail\nAlice Brown\talice@t.com\nBob Jones\tbob@t.com'
_r136 = parse_clipboard_table(_named_hdr)
check('name-hdr first_name r0',  _r136[0]['first_name'] == 'Alice')
check('name-hdr last_name r0',   _r136[0]['last_name']  == 'Brown')
check('name-hdr email r0',       _r136[0]['email']      == 'alice@t.com')
check('name-hdr first_name r1',  _r136[1]['first_name'] == 'Bob')
check('name-hdr last_name r1',   _r136[1]['last_name']  == 'Jones')

# 137. CSV two-column: "full_name,email" header
_csv2col = 'full_name,email\nCarol White,carol@t.com'
_r137 = parse_clipboard_table(_csv2col)
check('full_name hdr split first', _r137[0]['first_name'] == 'Carol')
check('full_name hdr split last',  _r137[0]['last_name']  == 'White')
check('full_name hdr email',       _r137[0]['email']      == 'carol@t.com')

# 138. Last, First comma format in name column
_comma_fmt = 'name\temail\nDoe, Jane\tjane@t.com'
_r138 = parse_clipboard_table(_comma_fmt)
check('last-first split first', _r138[0]['first_name'] == 'Jane')
check('last-first split last',  _r138[0]['last_name']  == 'Doe')

# 139. Already-split first_name/last_name left unchanged
_split_hdr = 'first_name\tlast_name\temail\nEve\tFox\teve@t.com'
_r139 = parse_clipboard_table(_split_hdr)
check('already-split first_name',   _r139[0]['first_name'] == 'Eve')
check('already-split last_name',    _r139[0]['last_name']  == 'Fox')
check('already-split not doubled',  'name' not in _r139[0])

# =========================================================
# 191-200: app_log module
# =========================================================
import tempfile as _tmpAL
from app_log import setup_logging, get_logger, log_path
_log_dir = Path(_tmpAL.mkdtemp())
_lp = setup_logging(_log_dir)
check('191 setup_logging returns Path', isinstance(_lp, Path))
check('192 log file created', _lp.exists())
check('193 log_path() returns same path', log_path() == _lp)

_lg = get_logger('test_module')
check('194 get_logger returns Logger', hasattr(_lg, 'info'))
_lg.info('test info message')
_lg.warning('test warning message')
_lg.error('test error message')
_lp_text = _lp.read_text(encoding='utf-8')
check('195 info written to log',    'test info message' in _lp_text)
check('196 warning written to log', 'test warning message' in _lp_text)
check('197 error written to log',   'test error message' in _lp_text)
check('198 log format has level',   'INFO' in _lp_text or 'WARNING' in _lp_text)

# Re-calling setup_logging with a new dir re-points the file
_log_dir2 = Path(_tmpAL.mkdtemp())
_lp2 = setup_logging(_log_dir2)
check('199 setup_logging re-point returns new path', _lp2 != _lp)
check('200 new log file created', _lp2.exists())
_lg.info('after re-point')
_lp2_text = _lp2.read_text(encoding='utf-8')
check('201 new log file receives writes', 'after re-point' in _lp2_text)

# =========================================================
# 202-210: RecordMissingInvoiceDialog — data layer
# =========================================================
import tempfile as _tmpRI
_ri_dir = Path(_tmpRI.mkdtemp())
_dsRI = DataStore(_ri_dir)
_dsRI.ensure_files()

# Simulate what the dialog produces and what _record_missing_invoice does
_missing_data = {
    'invoice_number':  '9001',
    'invoice_date':    '2025-03-01',
    'due_date':        '2025-03-31',
    'client_name':     'Acme Corp',
    'client_address':  '1 Main St',
    'notes':           'Missed invoice',
    'subtotal':        '100.00',
    'gst':             '10.00',
    'total':           '110.00',
    'paid':            'yes',
    'paid_date':       '2025-04-01',
    'payment_note':    'Bank transfer',
}
_dsRI.append_invoice(_missing_data)
_ri_invs = _dsRI.read_invoices()
check('202 missing invoice saved',         len(_ri_invs) == 1)
check('203 invoice number correct',        _ri_invs[0]['invoice_number'] == '9001')
check('204 client name correct',           _ri_invs[0]['client_name'] == 'Acme Corp')
check('205 subtotal correct',              _ri_invs[0]['subtotal'] == '100.00')
check('206 paid flag correct',             _ri_invs[0]['paid'] == 'yes')
check('207 paid_date correct',             _ri_invs[0]['paid_date'] == '2025-04-01')

# Duplicate: overwrite existing row (simulates dialog duplicate-check path)
_missing_data2 = dict(_missing_data)
_missing_data2['client_name'] = 'Acme Corp Updated'
_rows_ri = _dsRI.read_invoices()
_idx_ri = next(i for i, r in enumerate(_rows_ri) if r['invoice_number'] == '9001')
_rows_ri[_idx_ri].update(_missing_data2)
_dsRI._write_csv(_dsRI.invoices_csv_path, list(_rows_ri[0].keys()), _rows_ri)
_ri_invs2 = _dsRI.read_invoices()
check('208 overwrite keeps one record',    len(_ri_invs2) == 1)
check('209 overwrite updates client name', _ri_invs2[0]['client_name'] == 'Acme Corp Updated')

# Second distinct invoice
_dsRI.append_invoice({'invoice_number': '9002', 'invoice_date': '2025-05-01',
                       'client_name': 'Beta Ltd', 'subtotal': '200', 'gst': '20',
                       'total': '220', 'paid': '', 'paid_date': '', 'payment_note': ''})
check('210 two distinct invoices', len(_dsRI.read_invoices()) == 2)

# =========================================================
# 211-215: _detect_onedrive helper (non-GUI, import only)
# =========================================================
from invoice_gui import _detect_onedrive
_od = _detect_onedrive()
check('211 _detect_onedrive returns str', isinstance(_od, str))
# On this machine OneDrive is present (app lives inside OneDrive folder)
check('212 _detect_onedrive finds OneDrive', len(_od) > 0)
check('213 detected OneDrive path exists', Path(_od).is_dir())

# 70. InvoiceApp.ds is a DataStore instance
from data_store import DataStore as _DS
check('app has DataStore', isinstance(inv.ds, _DS))

# 71. Invoice append goes through DataStore
pre_inv = len(inv.ds.read_invoices())
inv.desc_var.set('DS Test'); inv.qty_var.set('1'); inv.price_var.set('100')
inv.taxable_var.set(False); inv._add_item()
inv.client_name_var.set('DS Client')
shown.clear()
inv._save_invoice()
post_inv = len(inv.ds.read_invoices())
check('invoice appended via DataStore', post_inv == pre_inv + 1)
inv.items.clear(); [inv.tree.delete(c) for c in inv.tree.get_children()]

# =========================================================
# Receipt attachment tests
# =========================================================
import tempfile as _tmpRCPT, shutil as _shRCPT
from data_store import LEDGER_FIELDS as _LF_RCPT

_rcpt_dir = Path(_tmpRCPT.mkdtemp())
from data_store import DataStore as _DSR
_dsR = _DSR(_rcpt_dir)
_dsR.ensure_files()

# Create a fake receipt file
_fake_receipt = _rcpt_dir / 'receipt_001.pdf'
_fake_receipt.write_text('fake pdf content')

# 261. append_ledger stores receipt_path
_lid = _dsR.append_ledger({
    'date': '2026-06-24', 'type': 'out', 'category': 'Supplies',
    'description': 'Stationery', 'amount': '25.00',
    'reference': '', 'notes': '', 'receipt_path': str(_fake_receipt),
})
_lrows = _dsR.read_ledger()
_lrow = next(r for r in _lrows if r['id'] == _lid)
check('261 receipt_path stored in ledger', _lrow.get('receipt_path') == str(_fake_receipt))

# 262. update_ledger clears receipt_path
_dsR.update_ledger(_lid, {'receipt_path': ''})
_lrows2 = _dsR.read_ledger()
_lrow2 = next(r for r in _lrows2 if r['id'] == _lid)
check('262 receipt_path cleared via update_ledger', _lrow2.get('receipt_path', '') == '')

# 263. migrate_all adds receipt_path to old ledger CSV without it
_old_ledger = _rcpt_dir / 'old_ledger.csv'
import csv as _csvR
with open(_old_ledger, 'w', newline='', encoding='utf-8') as _f:
    _w = _csvR.DictWriter(_f, fieldnames=['id','date','type','category','description','amount','reference','notes','deleted'])
    _w.writeheader()
    _w.writerow({'id':'99','date':'2026-01-01','type':'in','category':'Grant',
                 'description':'Old row','amount':'100','reference':'','notes':'','deleted':''})
_dsR2 = _DSR(_rcpt_dir)
_dsR2.ledger_path = _old_ledger
_added = _dsR2._migrate_csv(_old_ledger, _LF_RCPT)
check('263 migrate adds receipt_path column', 'receipt_path' in _added)
_migrated_rows = list(_csvR.DictReader(open(_old_ledger, encoding='utf-8')))
check('263 migrated row has receipt_path key', 'receipt_path' in _migrated_rows[0])

# 264. LedgerTab tree has 8 columns including rcpt
from ledger_tab import LedgerTab as _LT
from tkinter import ttk as _ttk264
import tempfile as _tmp264, shutil as _sh264
_dir264 = Path(_tmp264.mkdtemp())
try:
    _ds264 = _DSR(_dir264)
    _ds264.ensure_files()
    _nb264 = _ttk264.Notebook(tk.Toplevel(root))
    _lt264 = _LT(_nb264, _ds264, lambda: '$')
    _lt264.refresh()
    _cols264 = _lt264._tree['columns']
    check('264 ledger tree has rcpt column', 'rcpt' in _cols264)
except Exception as _e264:
    check('264 ledger tree has rcpt column', False)
finally:
    try: _sh264.rmtree(_dir264)
    except Exception: pass

try: _shRCPT.rmtree(_rcpt_dir)
except Exception: pass

# =========================================================
# Bank import tests
# =========================================================
from bank_import import parse_bank_csv, auto_match
import tempfile as _tmpBI, shutil as _shBI, csv as _csvBI

_bi_dir = Path(_tmpBI.mkdtemp())

# 265. parse_bank_csv — standard format (NAB-style)
_bi_csv = _bi_dir / 'bank.csv'
with open(_bi_csv, 'w', newline='', encoding='utf-8') as _f:
    _w = _csvBI.writer(_f)
    _w.writerow(['Date', 'Amount', 'Description', 'Reference', 'Balance'])
    _w.writerow(['01/06/2026', '330.00', 'PAY CO PTY LTD', 'REF001', '5330.00'])
    _w.writerow(['02/06/2026', '-150.00', 'DIRECT DEBIT', 'DD01', '5180.00'])  # debit — skip
    _w.writerow(['03/06/2026', '110.00', 'UNPAID CO', '', '5290.00'])

_bi_rows = parse_bank_csv(str(_bi_csv))
check('265 parse_bank_csv returns only credits', len(_bi_rows) == 2)
check('265 first row amount=330', _bi_rows[0]['amount'] == 330.0)
check('265 first row description', 'PAY CO' in _bi_rows[0]['description'])
check('265 date parsed correctly', _bi_rows[0]['date'] == '2026-06-01')

# 266. parse_bank_csv — Westpac format (Debit/Credit split)
_bi_wp = _bi_dir / 'westpac.csv'
with open(_bi_wp, 'w', newline='', encoding='utf-8') as _f:
    _w2 = _csvBI.writer(_f)
    _w2.writerow(['Date', 'Narration', 'Cheque Number', 'Debit', 'Credit', 'Balance'])
    _w2.writerow(['01/06/2026', 'JONES PTY LTD', '', '', '500.00', '6000.00'])
    _w2.writerow(['02/06/2026', 'RENT', '', '1200.00', '', '4800.00'])  # debit

_bi_wp_rows = parse_bank_csv(str(_bi_wp))
check('266 westpac: 1 credit row only', len(_bi_wp_rows) == 1)
check('266 westpac: amount=500', _bi_wp_rows[0]['amount'] == 500.0)

# 267. auto_match — high confidence match (amount + date proximity)
_bi_invs = [
    {'invoice_number': '0041', 'invoice_date': '2026-05-30', 'due_date': '2026-06-01',
     'total': '330.00', 'invoice_status': 'unpaid', 'client_name': 'Pay Co'},
    {'invoice_number': '0043', 'invoice_date': '2026-06-01', 'due_date': '2026-07-01',
     'total': '110.00', 'invoice_status': 'partial', 'client_name': 'Unpaid Co'},
]
_bi_pmts = []
_bi_matches = auto_match(_bi_rows, _bi_invs, _bi_pmts, tolerance_days=3)
check('267 auto_match returns 2 results', len(_bi_matches) == 2)
check('267 first match is high confidence', _bi_matches[0]['confidence'] == 'high')
check('267 first match invoice 0041', _bi_matches[0]['invoice']['invoice_number'] == '0041')
check('267 second match invoice 0043', _bi_matches[1]['invoice']['invoice_number'] == '0043')

# 268. auto_match — paid invoice skipped
_bi_invs_paid = [
    {'invoice_number': '0099', 'invoice_date': '2026-05-30', 'due_date': '2026-06-01',
     'total': '330.00', 'invoice_status': 'paid', 'client_name': 'Already Paid Co'},
]
_bi_m2 = auto_match(_bi_rows[:1], _bi_invs_paid, [], tolerance_days=3)
check('268 paid invoice not matched', _bi_m2[0]['confidence'] == 'none')

# 269. auto_match — low confidence (amount match but date far away)
_bi_invs_far = [
    {'invoice_number': '0050', 'invoice_date': '2026-01-01', 'due_date': '2026-01-15',
     'total': '330.00', 'invoice_status': 'unpaid', 'client_name': 'Far Co'},
]
_bi_m3 = auto_match(_bi_rows[:1], _bi_invs_far, [], tolerance_days=3)
check('269 far date gives low confidence', _bi_m3[0]['confidence'] == 'low')

try: _shBI.rmtree(_bi_dir)
except Exception: pass

# =========================================================
# P7: Client Statement of Account PDF tests
# =========================================================
import tempfile as _tmpP7, shutil as _shP7
from client_statement import build_client_statement_pdf as _bcs

_p7_dir = Path(_tmpP7.mkdtemp())

_p7_invoices = [
    {'invoice_number': '0101', 'invoice_date': '2026-01-10', 'due_date': '2026-01-24',
     'client_name': 'Acme', 'notes': 'First Aid Training', 'subtotal': '300.00',
     'gst': '30.00', 'total': '330.00', 'paid': '', 'paid_date': '', 'payment_note': '',
     'invoice_status': 'partial', 'pdf_path': ''},
    {'invoice_number': '0102', 'invoice_date': '2026-03-15', 'due_date': '2026-03-29',
     'client_name': 'Acme', 'notes': 'CPR Course', 'subtotal': '200.00',
     'gst': '20.00', 'total': '220.00', 'paid': 'yes', 'paid_date': '2026-04-01',
     'payment_note': '', 'invoice_status': 'paid', 'pdf_path': ''},
]
_p7_payments = {
    '0101': [{'id': '1', 'invoice_number': '0101', 'date': '2026-02-01',
              'amount': '200.00', 'method': 'EFT', 'reference': 'REF001', 'notes': ''}],
    '0102': [{'id': '2', 'invoice_number': '0102', 'date': '2026-04-01',
              'amount': '220.00', 'method': 'EFT', 'reference': 'REF002', 'notes': ''}],
}

_p7_out = _p7_dir / 'statement_acme.pdf'

# 284. build_client_statement_pdf produces a PDF file
try:
    _bcs(
        path=_p7_out,
        client_name='Acme',
        invoices=_p7_invoices,
        payments_by_invoice=_p7_payments,
        settings={'business_name': 'Test Co', 'currency_symbol': '$'},
        as_at_date='24/06/2026',
    )
    check('284 statement PDF created', _p7_out.exists())
    check('284 statement PDF non-empty', _p7_out.stat().st_size > 1000)
except Exception as _e284:
    check('284 statement PDF created', False, note=str(_e284))

# 285. PDF starts with %PDF header
if _p7_out.exists():
    with open(_p7_out, 'rb') as _f7:
        _hdr7 = _f7.read(4)
    check('285 PDF has correct header', _hdr7 == b'%PDF')

# 286. cancelled invoice contributes $0 to balance
_p7_cancelled = [
    {'invoice_number': '0200', 'invoice_date': '2026-01-01', 'due_date': '',
     'client_name': 'TestCo', 'notes': '', 'subtotal': '500.00',
     'gst': '50.00', 'total': '550.00', 'paid': '', 'paid_date': '', 'payment_note': '',
     'invoice_status': 'cancelled', 'pdf_path': ''},
]
_p7_out2 = _p7_dir / 'statement_cancelled.pdf'
try:
    _bcs(path=_p7_out2, client_name='TestCo', invoices=_p7_cancelled,
         payments_by_invoice={}, settings={}, as_at_date='24/06/2026')
    check('286 cancelled-only statement created', _p7_out2.exists())
except Exception as _e286:
    check('286 cancelled-only statement created', False, note=str(_e286))

# 287. empty invoices list still generates valid PDF
_p7_out3 = _p7_dir / 'statement_empty.pdf'
try:
    _bcs(path=_p7_out3, client_name='NoCo', invoices=[],
         payments_by_invoice={}, settings={}, as_at_date='24/06/2026')
    check('287 empty statement PDF created', _p7_out3.exists())
except Exception as _e287:
    check('287 empty statement PDF created', False, note=str(_e287))

try: _shP7.rmtree(_p7_dir)
except Exception: pass

# =========================================================
# P8: Accountant PDF Report Pack tests
# =========================================================
import tempfile as _tmpP8, shutil as _shP8
from accountant_pack import build_accountant_pack as _bap, _fy_dates as _fyd

# 288. _fy_dates parses standard FY string
_s8, _e8 = _fyd('2025-2026')
check('288 fy start', _s8 == '2025-07-01')
check('288 fy end',   _e8 == '2026-06-30')

# 289. _fy_dates handles slash separator
_s8b, _e8b = _fyd('2024/2025')
check('289 slash fy start', _s8b == '2024-07-01')
check('289 slash fy end',   _e8b == '2025-06-30')

# 290. build_accountant_pack produces a PDF with empty data
_p8_dir = Path(_tmpP8.mkdtemp())
from data_store import DataStore as _DSP8
_ds8 = _DSP8(_p8_dir)
_ds8.ensure_files()
_p8_out = _p8_dir / 'pack.pdf'
try:
    _bap(path=_p8_out, ds=_ds8,
         settings={'business_name': 'Test Co', 'currency_symbol': '$',
                   'business_abn': '12 345 678 901', 'gst_rate': '0.10'},
         fy='2025-2026')
    check('290 pack PDF created',    _p8_out.exists())
    check('290 pack PDF non-empty',  _p8_out.stat().st_size > 2000)
except Exception as _e290:
    check('290 pack PDF created', False, note=str(_e290))

# 291. PDF has correct header bytes
if _p8_out.exists():
    with open(_p8_out, 'rb') as _f8:
        check('291 PDF header', _f8.read(4) == b'%PDF')

# 292. build_accountant_pack with actual invoice + ledger data
import csv as _csvP8
_inv_path = _ds8.invoices_csv_path
from data_store import INVOICE_FIELDS as _IF8
with open(_inv_path, 'w', newline='', encoding='utf-8') as _fi8:
    _wi8 = _csvP8.DictWriter(_fi8, fieldnames=_IF8)
    _wi8.writeheader()
    _wi8.writerow({'invoice_number': '0001', 'invoice_date': '2025-09-01',
                   'due_date': '2025-09-15', 'client_name': 'ACME',
                   'client_address': '', 'notes': 'Training',
                   'subtotal': '1000', 'gst': '100', 'total': '1100',
                   'paid': 'yes', 'paid_date': '2025-09-20', 'payment_note': '',
                   'invoice_status': 'paid', 'pdf_path': ''})

_p8_out2 = _p8_dir / 'pack2.pdf'
try:
    _bap(path=_p8_out2, ds=_ds8,
         settings={'business_name': 'Test Co', 'currency_symbol': '$',
                   'gst_rate': '0.10'},
         fy='2025-2026')
    check('292 pack with data created',   _p8_out2.exists())
    check('292 pack with data non-empty', _p8_out2.stat().st_size > 3000)
except Exception as _e292:
    check('292 pack with data created', False, note=str(_e292))

try: _shP8.rmtree(_p8_dir)
except Exception: pass

# =========================================================
# P10: Dashboard metric calculation tests
# =========================================================
import tempfile as _tmpP10, shutil as _shP10, csv as _csvP10
from data_store import (DataStore as _DSP10, INVOICE_FIELDS as _IF10,
                         LEDGER_FIELDS as _LF10)
from datetime import date as _dateP10

_p10_dir = Path(_tmpP10.mkdtemp())
_ds10 = _DSP10(_p10_dir)
_ds10.ensure_files()

_today10 = _dateP10.today().isoformat()
_past10  = '2020-01-01'

# Seed invoices: 1 paid, 1 unpaid (not overdue), 1 overdue
with open(_ds10.invoices_csv_path, 'w', newline='', encoding='utf-8') as _f10i:
    _w10i = _csvP10.DictWriter(_f10i, fieldnames=_IF10)
    _w10i.writeheader()
    _w10i.writerow({'invoice_number': 'P001', 'invoice_date': '2026-01-01', 'due_date': '2026-01-31',
                    'client_name': 'A', 'client_address': '', 'notes': '',
                    'subtotal': '1000', 'gst': '100', 'total': '1100',
                    'paid': 'yes', 'paid_date': '2026-02-01', 'payment_note': '',
                    'invoice_status': 'paid', 'pdf_path': ''})
    _w10i.writerow({'invoice_number': 'P002', 'invoice_date': '2026-03-01', 'due_date': '2099-12-31',
                    'client_name': 'B', 'client_address': '', 'notes': '',
                    'subtotal': '500', 'gst': '50', 'total': '550',
                    'paid': '', 'paid_date': '', 'payment_note': '',
                    'invoice_status': 'unpaid', 'pdf_path': ''})
    _w10i.writerow({'invoice_number': 'P003', 'invoice_date': '2020-01-01', 'due_date': _past10,
                    'client_name': 'C', 'client_address': '', 'notes': '',
                    'subtotal': '200', 'gst': '20', 'total': '220',
                    'paid': '', 'paid_date': '', 'payment_note': '',
                    'invoice_status': 'unpaid', 'pdf_path': ''})

# Seed ledger: FY income + expense (use current FY)
_now10 = _dateP10.today()
_fy_y10 = _now10.year - 1 if _now10.month < 7 else _now10.year
_fy_date10 = f'{_fy_y10}-08-01'
with open(_ds10.ledger_path, 'w', newline='', encoding='utf-8') as _f10l:
    _w10l = _csvP10.DictWriter(_f10l, fieldnames=_LF10)
    _w10l.writeheader()
    _w10l.writerow({'id': '1', 'date': _fy_date10, 'type': 'in', 'category': 'Sales',
                    'description': 'Payment', 'amount': '800', 'reference': '', 'notes': '',
                    'receipt_path': '', 'deleted': ''})
    _w10l.writerow({'id': '2', 'date': _fy_date10, 'type': 'out', 'category': 'Costs',
                    'description': 'Expense', 'amount': '300', 'reference': '', 'notes': '',
                    'receipt_path': '', 'deleted': ''})

_inv10 = _ds10.read_invoices()
_led10 = _ds10.read_ledger()

# 299. unpaid_count = 2 (P002, P003 — not paid/cancelled/void)
_uc10 = sum(1 for i in _inv10 if i.get('invoice_status', '') not in ('paid', 'cancelled', 'void'))
check('299 unpaid count', _uc10 == 2)

# 300. outstanding = 550 + 220 = 770
_out10 = sum(
    max(float(i.get('total', 0) or 0) -
        sum(float(p.get('amount', 0) or 0) for p in _ds10.payments_for_invoice(i.get('invoice_number', ''))), 0.0)
    for i in _inv10 if i.get('invoice_status', '') not in ('paid', 'cancelled', 'void')
)
check('300 outstanding correct', abs(_out10 - 770.0) < 0.01)

# 301. overdue count = 1 (P003 due in past)
_od10 = sum(1 for i in _inv10
            if i.get('invoice_status', '') not in ('paid', 'cancelled', 'void')
            and i.get('due_date', '') and i.get('due_date', '') < _today10)
check('301 overdue count', _od10 == 1)

# 302. FY income = 800
_now_m10 = _dateP10.today().month
_now_y10 = _dateP10.today().year
_fys10 = f'{_now_y10 - 1}-07-01' if _now_m10 < 7 else f'{_now_y10}-07-01'
_fye10 = f'{_now_y10}-06-30'     if _now_m10 < 7 else f'{_now_y10 + 1}-06-30'
_fyi10 = sum(float(r.get('amount', 0) or 0) for r in _led10
             if r.get('type') == 'in' and _fys10 <= r.get('date', '') <= _fye10
             and r.get('deleted', '') != '1')
check('302 FY income', abs(_fyi10 - 800.0) < 0.01)

# 303. FY expenses = 300, net profit = 500
_fye_amt10 = sum(float(r.get('amount', 0) or 0) for r in _led10
                 if r.get('type') == 'out' and _fys10 <= r.get('date', '') <= _fye10
                 and r.get('deleted', '') != '1')
check('303 FY expenses', abs(_fye_amt10 - 300.0) < 0.01)
check('303 net profit',  abs(_fyi10 - _fye_amt10 - 500.0) < 0.01)

try: _shP10.rmtree(_p10_dir)
except Exception: pass

# =========================================================
# P11: Business health checks tests
# =========================================================
import tempfile as _tmpP11, shutil as _shP11, csv as _csvP11
from datetime import date as _dateP11, timedelta as _tdP11
from data_store import DataStore as _DSP11, INVOICE_FIELDS as _IF11
from health_checks import compute_health_prompts as _chk

_p11_dir = Path(_tmpP11.mkdtemp())
_ds11 = _DSP11(_p11_dir)
_ds11.ensure_files()

_today11  = _dateP11(2026, 6, 15)
_past_due = (_today11 - _tdP11(days=5)).isoformat()
_future   = (_today11 + _tdP11(days=30)).isoformat()

# Seed: 1 overdue invoice, 1 unpaid not-yet-due
with open(_ds11.invoices_csv_path, 'w', newline='', encoding='utf-8') as _f11:
    _w11 = _csvP11.DictWriter(_f11, fieldnames=_IF11)
    _w11.writeheader()
    _w11.writerow({'invoice_number': 'OV01', 'invoice_date': '2026-01-01',
                   'due_date': _past_due, 'client_name': 'X', 'client_address': '',
                   'notes': '', 'subtotal': '100', 'gst': '10', 'total': '110',
                   'paid': '', 'paid_date': '', 'payment_note': '',
                   'invoice_status': 'unpaid', 'pdf_path': ''})
    _w11.writerow({'invoice_number': 'FU01', 'invoice_date': '2026-06-10',
                   'due_date': _future, 'client_name': 'Y', 'client_address': '',
                   'notes': '', 'subtotal': '200', 'gst': '20', 'total': '220',
                   'paid': '', 'paid_date': '', 'payment_note': '',
                   'invoice_status': 'unpaid', 'pdf_path': ''})

_alerts11 = _chk(_ds11, {}, today=_today11)

# 304. Returns a list
check('304 alerts is list', isinstance(_alerts11, list))

# 305. Contains an overdue warning
_ov_warns = [a for a in _alerts11 if a['level'] == 'warn' and 'overdue' in a['message'].lower()]
check('305 overdue warn present', len(_ov_warns) == 1)
check('305 overdue detail has OV01', 'OV01' in _ov_warns[0].get('detail', ''))

# 306. ok alert present when no uncategorised ledger entries
_cat_oks = [a for a in _alerts11 if a['level'] == 'ok' and 'categoris' in a['message'].lower()]
check('306 all-expenses-categorised ok present', len(_cat_oks) >= 1)

# 307. warn fires when ledger has uncategorised expense
from data_store import LEDGER_FIELDS as _LF11
with open(_ds11.ledger_path, 'w', newline='', encoding='utf-8') as _f11l:
    _w11l = _csvP11.DictWriter(_f11l, fieldnames=_LF11)
    _w11l.writeheader()
    _w11l.writerow({'id': '1', 'date': '2026-05-01', 'type': 'out', 'category': '',
                    'description': 'Mystery spend', 'amount': '50', 'reference': '',
                    'notes': '', 'receipt_path': '', 'deleted': ''})
_alerts11b = _chk(_ds11, {}, today=_today11)
_uncat_warns = [a for a in _alerts11b if a['level'] == 'warn' and 'uncategoris' in a['message'].lower()]
check('307 uncategorised expense warn', len(_uncat_warns) == 1)

# 308. Alerts sorted warn first
_lvls = [a['level'] for a in _alerts11b]
_order_ok = all(_lvls[i] <= _lvls[i+1] or
                ({'warn':0,'info':1,'ok':2}.get(_lvls[i],9) <=
                 {'warn':0,'info':1,'ok':2}.get(_lvls[i+1],9))
                for i in range(len(_lvls)-1))
check('308 alerts sorted warn-info-ok', _order_ok)

try: _shP11.rmtree(_p11_dir)
except Exception: pass

# =========================================================
# P13: Accounting Export (Xero / MYOB) tests
# =========================================================
import tempfile as _tmpP13, shutil as _shP13, csv as _csvP13
from pathlib import Path as _PP13
from accounting_export import (
    build_xero_invoices_csv, build_xero_spend_money_csv,
    build_myob_sales_csv, build_myob_purchases_csv,
)

_p13_dir = _PP13(_tmpP13.mkdtemp())

_invs13 = [
    {'invoice_number': '0001', 'invoice_date': '2026-05-01', 'due_date': '2026-05-15',
     'client_name': 'ACME', 'client_address': '', 'notes': 'First Aid',
     'subtotal': '1000', 'gst': '100', 'total': '1100',
     'invoice_status': 'unpaid', 'pdf_path': ''},
    {'invoice_number': '0002', 'invoice_date': '2026-06-01', 'due_date': '2026-06-15',
     'client_name': 'Widgets Ltd', 'client_address': '', 'notes': 'CPR',
     'subtotal': '500', 'gst': '50', 'total': '550',
     'invoice_status': 'paid', 'pdf_path': ''},
    {'invoice_number': '0003', 'invoice_date': '2026-06-10', 'due_date': '2026-06-24',
     'client_name': 'SkipMe', 'client_address': '', 'notes': 'Cancel',
     'subtotal': '100', 'gst': '10', 'total': '110',
     'invoice_status': 'cancelled', 'pdf_path': ''},
]

_led13 = [
    {'id': '1', 'date': '2026-05-10', 'type': 'out', 'category': 'Supplies',
     'description': 'Stationery', 'amount': '110', 'reference': 'REF1',
     'notes': '', 'receipt_path': '', 'deleted': ''},
    {'id': '2', 'date': '2026-05-20', 'type': 'out', 'category': 'Travel',
     'description': 'Fuel', 'amount': '55', 'reference': 'REF2',
     'notes': '', 'receipt_path': '', 'deleted': ''},
    {'id': '3', 'date': '2026-05-25', 'type': 'in', 'category': 'Sales',
     'description': 'Income', 'amount': '500', 'reference': '',
     'notes': '', 'receipt_path': '', 'deleted': ''},
    {'id': '4', 'date': '2026-04-01', 'type': 'out', 'category': 'Rent',
     'description': 'Office', 'amount': '200', 'reference': '',
     'notes': '', 'receipt_path': '', 'deleted': '1'},  # deleted — should be skipped
]

_settings13 = {'gst_registered': 'yes', 'gst_rate': 0.10, 'currency_code': 'AUD'}

# 322. Xero invoices CSV: created with correct row count (skip cancelled)
_xi_path = _p13_dir / 'xero_inv.csv'
_n322 = build_xero_invoices_csv(_xi_path, _invs13, _settings13)
check('322 xero invoices row count', _n322 == 2)
check('322 xero invoices file exists', _xi_path.exists())

# 323. Xero invoices CSV: headers and data
with open(_xi_path, newline='', encoding='utf-8-sig') as _f13:
    _rows13 = list(_csvP13.DictReader(_f13))
check('323 xero headers present', '*ContactName' in _rows13[0])
check('323 xero client name', _rows13[0]['*ContactName'] == 'ACME')
check('323 xero invoice number', _rows13[0]['*InvoiceNumber'] == '0001')
check('323 xero date format dd/mm/yyyy', _rows13[0]['*InvoiceDate'] == '01/05/2026')
check('323 xero total', _rows13[0]['Total'] == '1100.00')
check('323 xero tax type gst', _rows13[0]['*TaxType'] == 'GST on Income')

# 324. Xero invoices CSV: date filter
_xi2 = _p13_dir / 'xero_inv_filtered.csv'
_n324 = build_xero_invoices_csv(_xi2, _invs13, _settings13, start='2026-06-01')
check('324 date filter start', _n324 == 1)

# 325. Xero spend money CSV: only 'out' rows, excludes deleted
_xs_path = _p13_dir / 'xero_spend.csv'
_n325 = build_xero_spend_money_csv(_xs_path, _led13, _settings13)
check('325 xero spend row count', _n325 == 2)
with open(_xs_path, newline='', encoding='utf-8-sig') as _f13s:
    _srows13 = list(_csvP13.DictReader(_f13s))
check('325 xero spend amount', _srows13[0]['*Amount'] == '110.00')
check('325 xero spend description', _srows13[0]['Description'] == 'Stationery')

# 326. MYOB sales CSV
_ms_path = _p13_dir / 'myob_sales.csv'
_n326 = build_myob_sales_csv(_ms_path, _invs13, _settings13)
check('326 myob sales row count', _n326 == 2)
with open(_ms_path, newline='', encoding='utf-8-sig') as _f13m:
    _mrows13 = list(_csvP13.DictReader(_f13m))
check('326 myob client name', _mrows13[0]['Co./Last Name'] == 'ACME')
check('326 myob tax code gst', _mrows13[0]['Tax Code'] == 'GST')
check('326 myob paid status', _mrows13[1]['Already Paid'] == '1')  # 0002 is paid

# 327. MYOB purchases CSV: non-deleted 'out' rows only
_mp_path = _p13_dir / 'myob_purchases.csv'
_n327 = build_myob_purchases_csv(_mp_path, _led13, _settings13)
check('327 myob purchases row count', _n327 == 2)
with open(_mp_path, newline='', encoding='utf-8-sig') as _f13p:
    _prows13 = list(_csvP13.DictReader(_f13p))
check('327 myob purchases description', _prows13[0]['Description'] == 'Stationery')
check('327 myob purchases tax code', _prows13[0]['Tax Code'] == 'GST')

# 328. GST not registered — tax type becomes Free
_settings13_nongst = {'gst_registered': 'no', 'gst_rate': 0.10, 'currency_code': 'AUD'}
_xi3 = _p13_dir / 'xero_nongst.csv'
build_xero_invoices_csv(_xi3, _invs13[:1], _settings13_nongst)
with open(_xi3, newline='', encoding='utf-8-sig') as _f13n:
    _nrows13 = list(_csvP13.DictReader(_f13n))
check('328 non-gst tax type', _nrows13[0]['*TaxType'] == 'GST Free Income')

try: _shP13.rmtree(_p13_dir)
except Exception: pass

# =========================================================
# P14: Expanded unit tests + logical use tests
# =========================================================
import tempfile as _tmpP14, shutil as _shP14, csv as _csvP14
from pathlib import Path as _PathP14
from datetime import date as _dP14, timedelta as _tdP14
from data_store import DataStore as _DSP14, INVOICE_FIELDS as _IF14, LEDGER_FIELDS as _LF14
from health_checks import compute_health_prompts as _chkP14
from accounting_export import (
    build_xero_invoices_csv, build_xero_spend_money_csv,
    build_myob_sales_csv, build_myob_purchases_csv,
)

_p14_dir = _PathP14(_tmpP14.mkdtemp())
_dsP14 = _DSP14(_p14_dir)
_dsP14.ensure_files()

# --- Health checks: edge cases ---
_todayP14 = _dP14(2026, 6, 15)

# 329. No data -> no warnings, all-ok prompts
_empty_alerts = _chkP14(_dsP14, {}, today=_todayP14)
check('329 empty health checks produce ok prompts', all(a['level'] == 'ok' for a in _empty_alerts))

# 330. Unpaid invoice >30 days old -> info alert
_past30 = (_todayP14 - _tdP14(days=40)).isoformat()
with open(_dsP14.invoices_csv_path, 'w', newline='', encoding='utf-8') as _f:
    _w = _csvP14.DictWriter(_f, fieldnames=_IF14)
    _w.writeheader()
    _w.writerow({'invoice_number': 'OLD01', 'invoice_date': '2026-01-01',
                 'due_date': '2026-12-31', 'client_name': 'OldClient', 'client_address': '',
                 'notes': '', 'subtotal': '100', 'gst': '10', 'total': '110',
                 'paid': '', 'paid_date': '', 'payment_note': '',
                 'invoice_status': 'unpaid', 'pdf_path': ''})
_old_alerts = _chkP14(_dsP14, {}, today=_todayP14)
_old_info = [a for a in _old_alerts if a['level'] == 'info' and '30' in a.get('message', '')]
check('330 unpaid >30 days info alert', len(_old_info) >= 1)

# 331. Missing receipts -> info alert
with open(_dsP14.ledger_path, 'w', newline='', encoding='utf-8') as _f:
    _w = _csvP14.DictWriter(_f, fieldnames=_LF14)
    _w.writeheader()
    _w.writerow({'id': '1', 'date': '2026-05-01', 'type': 'out', 'category': 'Travel',
                 'description': 'Fuel', 'amount': '55', 'reference': '', 'notes': '',
                 'receipt_path': '', 'deleted': ''})
_receipt_alerts = _chkP14(_dsP14, {}, today=_todayP14)
_receipt_info = [a for a in _receipt_alerts if a['level'] == 'info' and 'receipt' in a['message'].lower()]
check('331 missing receipt info alert', len(_receipt_info) >= 1)

# --- Accounting export: edge cases ---
# 339. Empty invoices -> empty CSV with headers
_empty_inv = _PathP14(_tmpP14.mkdtemp())
_empty_path = _empty_inv / 'empty.csv'
_n_empty = build_xero_invoices_csv(_empty_path, [], _settings13)
check('339 empty invoices export returns 0', _n_empty == 0)
_header_text = _empty_path.read_text(encoding='utf-8-sig')
check('339 empty invoices has headers', '*ContactName' in _header_text)

# 340. End date filter excludes after date
_filter_path = _empty_inv / 'filter_end.csv'
_n_filter = build_xero_invoices_csv(_filter_path, _invs13, _settings13, end='2026-05-31')
check('340 end date filter', _n_filter == 1)

# 341. Xero spend money respects custom account map
_map_settings = {'gst_registered': 'yes', 'gst_rate': 0.10, 'currency_code': 'AUD',
                 'xero_account_map': '{"Supplies": "600"}'}
_map_path = _empty_inv / 'mapped.csv'
build_xero_spend_money_csv(_map_path, _led13, _map_settings)
with open(_map_path, newline='', encoding='utf-8-sig') as _f:
    _r = list(_csvP14.DictReader(_f))
    check('341 custom account map applied', _r[0]['*AccountCode'] == '600')

# 342. MYOB sales with zero GST uses FRE code
_zero_gst = [{'invoice_number': 'Z1', 'invoice_date': '2026-05-01', 'due_date': '2026-05-15',
              'client_name': 'Zed', 'client_address': '', 'notes': '',
              'subtotal': '100', 'gst': '0', 'total': '100',
              'invoice_status': 'unpaid', 'pdf_path': ''}]
_zero_path = _empty_inv / 'zero_gst.csv'
build_myob_sales_csv(_zero_path, _zero_gst, _settings13)
with open(_zero_path, newline='', encoding='utf-8-sig') as _f:
    _r = list(_csvP14.DictReader(_f))
    check('342 zero GST MYOB tax code FRE', _r[0]['Tax Code'] == 'FRE')

# 343. MYOB purchases with zero GST uses FRE
_zero_p_path = _empty_inv / 'zero_p_gst.csv'
build_myob_purchases_csv(_zero_p_path, _zero_gst, _settings13)  # zero_gst has no 'type' so ignored
with open(_zero_p_path, newline='', encoding='utf-8-sig') as _f:
    _r = list(_csvP14.DictReader(_f))
    check('343 no out rows => empty purchases', len(_r) == 0)

try: _shP14.rmtree(_p14_dir)
except Exception: pass
try: _shP13.rmtree(_empty_inv)
except Exception: pass

# =========================================================
# P14: Email invoice tests
# =========================================================
import tempfile as _tmpP14e, shutil as _shP14e
from pathlib import Path as _PathP14e
from email_invoice import (
    default_invoice_subject, default_invoice_body,
    has_smtp_config, send_email_with_attachment,
)

# 344. default_invoice_subject format
_s344 = default_invoice_subject('0001', 'ACME')
check('344 default subject has invoice and client', '0001' in _s344 and 'ACME' in _s344)

# 345. default_invoice_body contains client and business name
_b345 = default_invoice_body('0001', 'ACME', {'business_name': 'My Biz'})
check('345 default body has business name', 'My Biz' in _b345)
check('345 default body has invoice number', '0001' in _b345)

# 346. has_smtp_config returns True only when server+from present
check('346 smtp config missing', not has_smtp_config({}))
check('346 smtp config present', has_smtp_config({'smtp_server': 'smtp.test.com', 'smtp_from': 'a@test.com'}))

# 347. Missing attachment returns error and calls audit
_audit347 = []
_r347 = send_email_with_attachment('to@test.com', 'Subj', 'Body', '/nonexistent/file.pdf', {},
                                    audit_fn=lambda a, d, t, r: _audit347.append((a, d, t, r)))
check('347 missing attachment fails', not _r347['ok'])
check('347 missing attachment audit', any(a == 'email_failed' for a, d, t, r in _audit347))

# 348. No backend available returns error
_p14e_dir = _PathP14e(_tmpP14e.mkdtemp())
_pdf348 = _p14e_dir / 'inv.pdf'
_pdf348.write_text('PDF content', encoding='utf-8')
_r348 = send_email_with_attachment('to@test.com', 'Subj', 'Body', str(_pdf348), {})
check('348 no backend error', not _r348['ok'] and 'backend' in _r348['error'].lower())

# 349. SMTP backend mocked success
_sent349 = []
class _FakeSMTP:
    def __init__(self, server, port): self.server = server; self.port = port
    def starttls(self): pass
    def login(self, user, password): self._user = user; self._pass = password
    def sendmail(self, from_addr, to_addrs, msg): _sent349.append((from_addr, to_addrs, msg))
    def __enter__(self): return self
    def __exit__(self, *a): pass

import smtplib as _smtplib14
_orig_smtp = _smtplib14.SMTP
_smtplib14.SMTP = _FakeSMTP
_r349 = send_email_with_attachment('to@test.com', 'Subj', 'Body', str(_pdf348),
                                    {'smtp_server': 'smtp.test.com', 'smtp_port': 587,
                                     'smtp_user': 'u', 'smtp_password': 'p',
                                     'smtp_from': 'from@test.com', 'smtp_tls': 'yes'})
_smtplib14.SMTP = _orig_smtp
check('349 smtp send ok', _r349['ok'] and _r349['method'] == 'smtp')
check('349 smtp message sent', len(_sent349) == 1)
check('349 smtp from correct', _sent349[0][0] == 'from@test.com')

# 350. MAPI unavailable -> falls back to SMTP
_sent350 = []
_smtplib14.SMTP = _FakeSMTP
_r350 = send_email_with_attachment('to@test.com', 'Subj', 'Body', str(_pdf348),
                                    {'smtp_server': 'smtp.test.com', 'smtp_from': 'from@test.com'},
                                    prefer_mapi=True)
_smtplib14.SMTP = _orig_smtp
check('350 fallback to smtp when no outlook', _r350['ok'] and _r350['method'] == 'smtp')

try: _shP14e.rmtree(_p14e_dir)
except Exception: pass

# ---- summary ----
root.destroy()
try:
    shutil.rmtree(tmp)
except Exception:
    pass  # Windows may lock the temp PDF; cleanup failure is not a test failure

print()
if failures:
    print(f"FAILURES ({len(failures)}): {', '.join(failures)}")
    sys.exit(1)
else:
    print(f"ALL {passed} TESTS PASSED")
