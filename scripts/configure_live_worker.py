"""Private credential dialog for the local worker; never prints credentials."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from urllib.parse import urlsplit

base = Path(__file__).resolve().parent.parent
target = base / 'tmp' / 'live-worker.json'
data = json.loads(target.read_text()) if target.exists() else {}
local = base / 'delivery.local.json'
if local.exists():
    for key, value in json.loads(local.read_text()).items():
        data.setdefault(key, value)
secret_file = base / 'tmp' / 'render-secret.env'
if secret_file.exists():
    data.setdefault('SECRET_KEY', secret_file.read_text().strip().split('=', 1)[1])
data.setdefault('SITE_URL', 'https://book-my-show-2ns5.onrender.com')

root = tk.Tk()
root.title('Book My Show - Live email worker')
root.geometry('700x620')
tk.Label(root, text='Connect this computer to live ticket deliveries', font=('Arial', 14, 'bold')).pack(pady=14)
tk.Label(root, text='Private values stay in an ignored file on this computer.\nDo not paste credentials into chat.', justify='left').pack()
fields = {}
for key, title, hidden in [
    ('DATABASE_URL', 'Render PostgreSQL → Info → Connections → External Database URL', True),
    ('SECRET_KEY', 'Same SECRET_KEY as Render Environment (prefilled from generated file)', True),
    ('SITE_URL', 'Public website URL', False),
    ('EMAIL_HOST_USER', 'Gmail sender address', False),
    ('EMAIL_HOST_PASSWORD', 'Google 16-letter app password (not your Gmail password)', True),
]:
    tk.Label(root, text=title, anchor='w').pack(fill='x', padx=24, pady=(14, 3))
    field = tk.Entry(root, width=85, show='*' if hidden else '')
    field.insert(0, data.get(key, ''))
    field.pack(padx=24, fill='x')
    fields[key] = field


def save():
    values = {key: field.get().strip() for key, field in fields.items()}
    values['EMAIL_HOST_PASSWORD'] = ''.join(values['EMAIL_HOST_PASSWORD'].split())
    if not all(values.values()):
        messagebox.showerror('Missing details', 'Complete every field. If no PostgreSQL database exists in Render, tell Codex.')
        return
    if urlsplit(values['DATABASE_URL']).scheme not in ('postgres', 'postgresql'):
        messagebox.showerror('Database URL', 'Use the External PostgreSQL Database URL from Render.')
        return
    if not values['SITE_URL'].startswith('https://') or len(values['EMAIL_HOST_PASSWORD']) != 16:
        messagebox.showerror('Check details', 'Use an HTTPS website URL and a 16-letter Gmail app password.')
        return
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(values, indent=2), encoding='utf-8')
    for field in fields.values():
        field.delete(0, tk.END)
    messagebox.showinfo('Saved', 'Private settings saved. Reply SAVED in chat so the connection can be tested.')
    root.destroy()


tk.Button(root, text='Save private settings', command=save, padx=20, pady=8).pack(pady=20)
tk.Label(root, text='This worker sends email only while this computer is awake and online.').pack()
root.mainloop()
