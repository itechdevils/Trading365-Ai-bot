"""Trading 365 FB Manager v0.2: local browser profiles, group library, review scheduler."""
import csv
import sys
from agent_features import parse_command
from login_features import sign_in
import json
import os
import re
import subprocess
import threading
import tkinter as tk
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog, filedialog

ROOT = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'Trading365' / 'FBManagerV02'
DB = ROOT / 'data.json'
PROFILES = ROOT / 'profiles'
ROOT.mkdir(parents=True, exist_ok=True)
PROFILES.mkdir(parents=True, exist_ok=True)

def chrome_path():
    candidates = [Path(os.environ.get(k, '')) / 'Google/Chrome/Application/chrome.exe' for k in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA')]
    return next((str(p) for p in candidates if p.is_file()), None)

def safe_group_link(value):
    value = value.strip()
    if re.fullmatch(r'\d{3,25}', value):
        return 'https://www.facebook.com/groups/' + value
    if not value.startswith('https://'):
        raise ValueError('Use numeric group ID or https://www.facebook.com/groups/... URL')
    p = urllib.parse.urlparse(value)
    if p.hostname not in ('facebook.com', 'www.facebook.com', 'm.facebook.com') or not p.path.startswith('/groups/'):
        raise ValueError('Only Facebook group links are accepted')
    return urllib.parse.urlunparse(('https', 'www.facebook.com', p.path.rstrip('/')+'/', '', '', ''))

def read_data():
    try:
        data = json.loads(DB.read_text('utf-8'))
        if isinstance(data, dict):
            return {'accounts':data.get('accounts', []), 'groups':data.get('groups', []), 'tasks':data.get('tasks', [])}
    except (OSError, ValueError):
        pass
    return {'accounts':[], 'groups':[], 'tasks':[]}

class Manager:
    def __init__(self, root):
        self.root = root
        self.data = read_data()
        self.procs = {}
        self.drivers = {}
        self.temp_credentials = {}
        self.agent_mode = tk.StringVar(value="Manual")
        self.root.title('Trading 365 | FB Account & Group Manager v0.3 AI Agent')
        self.root.geometry('1130x770')
        self.root.minsize(890, 600)
        self.status = tk.StringVar(value='Ready')
        self.build()
        self.refresh()
        self.root.after(10000, self.tick)
        self.root.protocol('WM_DELETE_WINDOW', self.quit)

    def save(self):
        temp = DB.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), 'utf-8')
        temp.replace(DB)

    def bar(self, parent, items):
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=8)
        for label, command in items:
            ttk.Button(frame, text=label, command=command).pack(side='left', padx=(0, 7))

    def table(self, parent, cols):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, pady=8)
        table = ttk.Treeview(frame, columns=[x[0] for x in cols], show='headings', selectmode='browse')
        for key, label, width in cols:
            table.heading(key, text=label)
            table.column(key, width=width, minwidth=75)
        table.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=table.yview)
        scroll.pack(side='right', fill='y')
        table.configure(yscrollcommand=scroll.set)
        return table

    def build(self):
        title = ttk.Frame(self.root, padding=(16, 12))
        title.pack(fill='x')
        ttk.Label(title, text='T365  /  FB ACCOUNT & GROUP MANAGER', font=('Segoe UI', 19, 'bold')).pack(anchor='w')
        ttk.Label(title, text='Independent local manager • User-approved group actions • No passwords stored').pack(anchor='w')
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill='both', expand=True, padx=16, pady=8)
        a = ttk.Frame(self.tabs, padding=12)
        g = ttk.Frame(self.tabs, padding=12)
        q = ttk.Frame(self.tabs, padding=12)
        ai = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(a, text='Accounts / Profiles')
        self.tabs.add(g, text='Group Library')
        self.tabs.add(q, text='Post & Join Review Queue')
        self.tabs.add(ai, text='Local AI Assistant')
        self.bar(a, [('Add Profile',self.add_account),('Import Accounts CSV',self.import_accounts),('Secure Login',self.secure_login),('Login Imported',self.login_imported),('Open / Focus',self.open_account),('Stop Browser',self.stop_account),('Remove Profile',self.remove_account)])
        self.account_table = self.table(a,[('name','Account Label',300),('id','Profile',100),('status','Browser Status',180)])
        ttk.Label(a, text='Select account and use Secure Login; OTP/CAPTCHA must be completed manually. CSV passwords are kept in RAM only.').pack(anchor='w')
        self.bar(g, [('Add Group ID / Link',self.add_group),('Import Groups CSV',self.import_groups),('Find by Keyword',self.search_groups),('Open Group',self.open_group),('Remove Group',self.remove_group)])
        self.group_table = self.table(g,[('name','Group Label',270),('keyword','Keyword',210),('url','Facebook Group URL',430)])
        ttk.Label(g, text='Discovery opens Facebook search for your review. Membership is not inferred or automatically verified.').pack(anchor='w')
        settings = ttk.Frame(q)
        settings.pack(fill='x', pady=4)
        ttk.Label(settings, text='Selected account:').grid(row=0,column=0,sticky='w',padx=5,pady=4)
        self.account_pick = ttk.Combobox(settings, state='readonly', width=25)
        self.account_pick.grid(row=0,column=1,padx=5,pady=4)
        ttk.Label(settings, text='Keyword filter:').grid(row=0,column=2,padx=5,pady=4)
        self.keyword = ttk.Entry(settings, width=24)
        self.keyword.grid(row=0,column=3,padx=5,pady=4)
        ttk.Label(settings, text='Max groups:').grid(row=1,column=0,sticky='w',padx=5,pady=4)
        self.max_groups = ttk.Spinbox(settings, from_=1,to=500,width=8)
        self.max_groups.set('10')
        self.max_groups.grid(row=1,column=1,sticky='w',padx=5,pady=4)
        ttk.Label(settings, text='Review interval (minutes):').grid(row=1,column=2,sticky='w',padx=5,pady=4)
        self.interval = ttk.Spinbox(settings, from_=1,to=10080,width=10)
        self.interval.set('60')
        self.interval.grid(row=1,column=3,sticky='w',padx=5,pady=4)
        ttk.Label(settings, text='Facebook post link:').grid(row=2,column=0,sticky='w',padx=5,pady=4)
        self.post_link = ttk.Entry(settings, width=65)
        self.post_link.grid(row=2,column=1,columnspan=3,sticky='ew',padx=5,pady=4)
        self.bar(q, [('Queue Join Reviews',lambda:self.queue('join')),('Queue Post Reviews',lambda:self.queue('post')),('Open Selected for Approval',self.open_task),('Mark Done',self.mark_done),('Delete Task',self.delete_task)])
        self.task_table = self.table(q,[('kind','Task',110),('account','Account',130),('group','Group',230),('due','Review Time',170),('status','Status',180)])
        ttk.Label(q, text='At the scheduled time the task becomes Ready for review. No unattended joining or posting.').pack(anchor='w')
        ttk.Label(ai, text='Trading 365 AI Agent — local commands + Ollama assistant',font=('Segoe UI',13,'bold')).pack(anchor='w',pady=12)
        mode_row=ttk.Frame(ai);mode_row.pack(fill='x',pady=6)
        ttk.Label(mode_row,text='Agent mode:').pack(side='left')
        ttk.Combobox(mode_row,textvariable=self.agent_mode,values=['Manual','Autonomous'],state='readonly',width=15).pack(side='left',padx=8)
        ttk.Label(mode_row,text='Autonomous only runs allowlisted local commands; login requires secure input.').pack(side='left')
        ttk.Label(ai, text='Requires Ollama installed and a model downloaded, e.g. ollama pull llama3.2').pack(anchor='w')
        ttk.Label(ai, text='Model:').pack(anchor='w',pady=(12,0))
        self.model = ttk.Entry(ai, width=30)
        self.model.insert(0,'llama3.2')
        self.model.pack(anchor='w')
        ttk.Label(ai, text='Ask in Roman Urdu or English:').pack(anchor='w',pady=(12,0))
        self.ai_prompt = ttk.Entry(ai)
        self.ai_prompt.pack(fill='x',pady=4)
        self.ai_prompt.insert(0,'Mere profiles aur scheduled tasks ka status batao')
        self.bar(ai,[('Execute / Ask Agent',self.agent_command),('Listen (Windows)',self.listen_voice),('Speak Last Reply',self.speak_reply),('Ask Ollama Only',self.ask_ai)])
        self.ai_output = tk.Text(ai,height=12,wrap='word')
        self.ai_output.pack(fill='both',expand=True,pady=8)
        ttk.Label(self.root,textvariable=self.status,padding=(16,5)).pack(fill='x')
        ttk.Label(self.root,text='Developed by Mazhar Rafiq • Powered by Trading 365 Software Solutions',padding=(16,6)).pack()

    def selected(self, table, key):
        sel = table.selection()
        if not sel:
            messagebox.showinfo('Selection required','Select a row first.')
            return None
        return next((x for x in self.data[key] if x['id']==sel[0]),None)

    def next_id(self, key, prefix):
        ids = [int(x['id'][1:]) for x in self.data[key] if x['id'].startswith(prefix) and x['id'][1:].isdigit()]
        return f'{prefix}{max(ids,default=0)+1:04d}'

    def add_account(self):
        name = simpledialog.askstring('Add profile','Account label (no password):',parent=self.root)
        if name and name.strip():
            self.data['accounts'].append({'id':self.next_id('accounts','P'),'name':name.strip()})
            self.save(); self.refresh()

    def import_accounts(self):
        path = filedialog.askopenfilename(filetypes=[('CSV files','*.csv')])
        if not path:return
        try:
            with open(path,encoding='utf-8-sig',newline='') as f:
                rows=list(csv.DictReader(f))
            added=0
            for row in rows:
                name=(row.get('name') or row.get('label') or row.get('username') or '').strip()
                if name:
                    account_id=self.next_id('accounts','P')
                    self.data['accounts'].append({'id':account_id,'name':name})
                    username=(row.get('username') or row.get('email') or '').strip()
                    password=(row.get('password') or '').strip()
                    if username and password:self.temp_credentials[account_id]=(username,password)
                    added+=1
            self.save();self.refresh()
            messagebox.showinfo('Imported',f'Imported {added} account labels. Credentials, if provided, remain only in memory until this app closes. Login each with explicit confirmation.')
        except (OSError,UnicodeError,csv.Error) as e:messagebox.showerror('CSV error',str(e))

    def secure_login(self):
        account=self.selected(self.account_table,'accounts')
        if not account:return
        if account['id'] in self.drivers:
            messagebox.showinfo('Browser active','Close the previous automated browser before starting a new sign-in for this profile.');return
        running=self.procs.get(account['id'])
        if running and running.poll() is None:
            messagebox.showwarning('Profile in use','Close this profile Chrome window first, then retry Secure Login.');return
        username,password=self.temp_credentials.pop(account['id'],('',''))
        dialog=tk.Toplevel(self.root);dialog.title('Secure login - '+account['name']);dialog.geometry('450x225');dialog.transient(self.root);dialog.grab_set()
        ttk.Label(dialog,text='Authorized Facebook account only',font=('Segoe UI',11,'bold')).pack(pady=10)
        ttk.Label(dialog,text='Email / phone:').pack(anchor='w',padx=20)
        u=ttk.Entry(dialog,width=52);u.insert(0,username);u.pack(padx=20)
        ttk.Label(dialog,text='Password (not saved):').pack(anchor='w',padx=20,pady=(7,0))
        pw=ttk.Entry(dialog,width=52,show='*');pw.insert(0,password);pw.pack(padx=20)
        def submit():
            user=u.get().strip();secret=pw.get()
            if not user or not secret:messagebox.showwarning('Missing','Enter username and password.',parent=dialog);return
            dialog.destroy()
            if not messagebox.askyesno('Confirm login','Attempt sign-in for '+account['name']+'?\nComplete 2FA/CAPTCHA yourself if prompted.'):return
            self.status.set('Launching Chrome for secure login...')
            def work():
                try:
                    driver=sign_in(PROFILES/account['id'],user,secret)
                    self.drivers[account['id']]=driver
                    self.root.after(0,lambda:self.status.set('Login submitted. Verify account in Chrome; 2FA may be required.'))
                except Exception as exc:
                    msg=str(exc)[:800]
                    self.root.after(0,lambda:messagebox.showerror('Login error',msg))
            threading.Thread(target=work,daemon=True).start()
        ttk.Button(dialog,text='Start Login',command=submit).pack(pady=14)

    def login_imported(self):
        count=len(self.temp_credentials)
        if not count:messagebox.showinfo('No pending credentials','Import CSV with name,username,password columns. Credentials are never saved.');return
        messagebox.showinfo('Imported credentials',f'{count} accounts have temporary credentials in memory. Select each account and click Secure Login to review and sign in individually.')

    def agent_command(self):
        question=self.ai_prompt.get().strip()
        if not question:return
        parsed=parse_command(question)
        action=parsed['action']
        if action=='unknown':self.ask_ai();return
        if action=='status':
            result=f"Profiles: {len(self.data['accounts'])} | Groups: {len(self.data['groups'])} | Review tasks: {len(self.data['tasks'])}. Pending: {sum(t['status']!='Marked done by user' for t in self.data['tasks'])}."
        elif action=='create_profiles':
            count=parsed['count']
            if not 1<=count<=100:result='Create 1-100 profiles per request.'
            elif self.agent_mode.get()=='Manual' and not messagebox.askyesno('Approve agent action',f'Create {count} local Chrome profiles?'):return
            else:
                for _ in range(count):
                    pid=self.next_id('accounts','P');self.data['accounts'].append({'id':pid,'name':'Phone '+pid[1:]})
                self.save();self.refresh();result=f'Created {count} profile records.'
        elif action=='open_profile':
            number=parsed['number'];account=next((a for a in self.data['accounts'] if int(a['id'][1:])==number),None)
            if not account:result=f'Profile {number} not found.'
            elif self.agent_mode.get()=='Manual' and not messagebox.askyesno('Approve agent action',f'Open {account["name"]}?'):return
            else:self.launch(account,'https://www.facebook.com/');result=f'Open requested for {account["name"]}.'
        elif action=='open_group':
            if self.agent_mode.get()=='Manual' and not messagebox.askyesno('Approve agent action','Open group '+parsed['group_id']+'?'):return
            import webbrowser
            webbrowser.open('https://www.facebook.com/groups/'+parsed['group_id'])
            result='Opened group page. Membership actions require your approval.'
        else:result='Unsupported command.'
        self.display_ai(result)

    def listen_voice(self):
        if sys.platform!='win32':messagebox.showinfo('Windows only','Windows Speech Recognition is available on Windows only.');return
        self.status.set('Listening for one command (up to 8 seconds)...')
        ps=r"""Add-Type -AssemblyName System.Speech; $r=New-Object System.Speech.Recognition.SpeechRecognitionEngine; $r.SetInputToDefaultAudioDevice(); $r.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar)); $x=$r.Recognize([TimeSpan]::FromSeconds(8)); if($x){[Console]::Write($x.Text)}"""
        def work():
            try:
                res=subprocess.run(['powershell','-NoProfile','-Command',ps],capture_output=True,text=True,timeout=18,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                heard=res.stdout.strip()
                if res.returncode!=0:heard=''
                self.root.after(0,lambda:self.voice_result(heard))
            except Exception as exc:self.root.after(0,lambda:self.status.set('Voice unavailable: '+str(exc)[:120]))
        threading.Thread(target=work,daemon=True).start()

    def voice_result(self,heard):
        if heard:
            self.ai_prompt.delete(0,'end');self.ai_prompt.insert(0,heard)
            self.status.set('Heard: '+heard+' — review and click Execute / Ask Agent.')
        else:self.status.set('Speech not recognized. Windows speech language and microphone settings may need configuration.')

    def speak_reply(self):
        if sys.platform!='win32':return
        answer=self.ai_output.get('1.0','end').strip()[:1200]
        if not answer:return
        ps='Add-Type -AssemblyName System.Speech; $v=New-Object System.Speech.Synthesis.SpeechSynthesizer; $v.Speak($args[0])'
        threading.Thread(target=lambda:subprocess.run(['powershell','-NoProfile','-Command',ps,answer],capture_output=True,timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)),daemon=True).start()

    def launch(self, account, url):
        chrome=chrome_path()
        if not chrome:
            messagebox.showerror('Chrome missing','Google Chrome not found on this Windows PC.')
            return
        profile=PROFILES/account['id']
        profile.mkdir(parents=True,exist_ok=True)
        try:
            existing=self.procs.get(account['id'])
            if existing and existing.poll() is None:
                subprocess.Popen([chrome,'--new-window',url])
            else:
                self.procs[account['id']]=subprocess.Popen([chrome,f'--user-data-dir={profile}','--no-first-run','--new-window',url])
            self.refresh()
        except OSError as e:messagebox.showerror('Chrome launch error',str(e))

    def open_account(self):
        account=self.selected(self.account_table,'accounts')
        if account:self.launch(account,'https://www.facebook.com/')

    def stop_account(self):
        account=self.selected(self.account_table,'accounts')
        if not account:return
        driver=self.drivers.pop(account['id'],None)
        if driver:
            try:driver.quit()
            except Exception:pass
        proc=self.procs.get(account['id'])
        if proc and proc.poll() is None:
            proc.terminate()
            self.status.set('Requested browser stop; Chrome may keep child processes running.')
        self.refresh()

    def remove_account(self):
        account=self.selected(self.account_table,'accounts')
        if account and messagebox.askyesno('Remove label','Remove this profile from dashboard? Its Chrome data folder will be preserved.'):
            self.data['accounts'].remove(account)
            self.save();self.refresh()

    def add_group(self):
        value=simpledialog.askstring('Add group','Facebook group numeric ID or full group URL:',parent=self.root)
        if not value:return
        try:url=safe_group_link(value)
        except ValueError as e:messagebox.showerror('Invalid group',str(e));return
        if any(g['url']==url for g in self.data['groups']):
            messagebox.showinfo('Duplicate','This group is already saved.');return
        name=simpledialog.askstring('Group label','Group name / label:',parent=self.root) or url.rsplit('/',2)[-2]
        keyword=simpledialog.askstring('Keyword','Keyword/category (optional):',parent=self.root) or ''
        self.data['groups'].append({'id':self.next_id('groups','G'),'name':name.strip(),'keyword':keyword.strip(),'url':url})
        self.save();self.refresh()

    def import_groups(self):
        path=filedialog.askopenfilename(filetypes=[('CSV files','*.csv')])
        if not path:return
        added=0;skipped=0
        try:
            with open(path,encoding='utf-8-sig',newline='') as f:
                for row in csv.DictReader(f):
                    try:
                        url=safe_group_link(row.get('url') or row.get('group_id') or row.get('link') or '')
                        if any(g['url']==url for g in self.data['groups']):skipped+=1;continue
                        self.data['groups'].append({'id':self.next_id('groups','G'),'name':(row.get('name') or url).strip(),'keyword':(row.get('keyword') or '').strip(),'url':url})
                        added+=1
                    except ValueError:skipped+=1
            self.save();self.refresh();messagebox.showinfo('Import',f'Added {added} groups; skipped {skipped} invalid/duplicate entries.')
        except (OSError,UnicodeError,csv.Error) as e:messagebox.showerror('CSV error',str(e))

    def search_groups(self):
        word=simpledialog.askstring('Discover groups','Keyword to search on Facebook:',parent=self.root)
        if not word:return
        import webbrowser
        webbrowser.open('https://www.facebook.com/search/groups/?q='+urllib.parse.quote(word.strip()))
        messagebox.showinfo('Review search results','Review results in Facebook. Save approved groups by ID or URL using Add Group ID / Link.')

    def open_group(self):
        group=self.selected(self.group_table,'groups')
        if group:
            import webbrowser
            webbrowser.open(group['url'])

    def remove_group(self):
        group=self.selected(self.group_table,'groups')
        if group and messagebox.askyesno('Remove group','Remove saved group? Existing review tasks will remain.'):
            self.data['groups'].remove(group);self.save();self.refresh()

    def queue(self,kind):
        selected=self.account_pick.get()
        account=next((a for a in self.data['accounts'] if selected.startswith(a['id']+' | ')),None)
        if not account:messagebox.showwarning('Account required','Choose an account.');return
        try:
            maximum=int(self.max_groups.get());minutes=int(self.interval.get())
            if not 1<=maximum<=500 or not 1<=minutes<=10080:raise ValueError()
        except ValueError:messagebox.showerror('Invalid settings','Max groups: 1-500; interval: 1-10080 minutes.');return
        url=self.post_link.get().strip()
        if kind=='post':
            parsed=urllib.parse.urlparse(url)
            if parsed.scheme!='https' or parsed.hostname not in ('facebook.com','www.facebook.com','m.facebook.com','fb.watch'):
                messagebox.showerror('Invalid link','Enter a valid HTTPS Facebook post link.');return
        keyword=self.keyword.get().strip().casefold()
        groups=[g for g in self.data['groups'] if not keyword or keyword in (g['name']+' '+g['keyword']).casefold()][:maximum]
        if not groups:messagebox.showwarning('No groups','Add groups or change keyword filter.');return
        now=datetime.now()
        count=0
        for i,g in enumerate(groups):
            if any(t['account_id']==account['id'] and t['group_url']==g['url'] and t['kind']==kind and t.get('post_url','')==url for t in self.data['tasks']):continue
            self.data['tasks'].append({'id':self.next_id('tasks','T'),'kind':kind,'account_id':account['id'],'account':account['name'],'group':g['name'],'group_url':g['url'],'post_url':url if kind=='post' else '', 'due':(now+timedelta(minutes=minutes*i)).isoformat(timespec='minutes'),'status':'Scheduled'})
            count+=1
        self.save();self.refresh()
        messagebox.showinfo('Review tasks',f'{count} review tasks queued. The software does not auto-click Join or Share.')

    def open_task(self):
        task=self.selected(self.task_table,'tasks')
        if not task:return
        account=next((a for a in self.data['accounts'] if a['id']==task['account_id']),None)
        if not account:messagebox.showerror('Missing account','Account label has been removed.');return
        self.launch(account,task['group_url'])
        if task['kind']=='post':
            messagebox.showinfo('Post for review','Open the Facebook post link below in your profile, then manually share it only where you have permission:\n\n'+task['post_url'])
        else:
            messagebox.showinfo('Join review','Review group rules and membership questions. Submit a join request manually if appropriate.')
        task['status']='Awaiting manual confirmation'
        self.save();self.refresh()

    def mark_done(self):
        task=self.selected(self.task_table,'tasks')
        if task and messagebox.askyesno('Confirm','Have you completed this action yourself in Facebook?'):
            task['status']='Marked done by user';self.save();self.refresh()

    def delete_task(self):
        task=self.selected(self.task_table,'tasks')
        if task:self.data['tasks'].remove(task);self.save();self.refresh()

    def tick(self):
        now=datetime.now()
        changed=False;ready=0
        for task in self.data['tasks']:
            if task['status']=='Scheduled' and datetime.fromisoformat(task['due'])<=now:
                task['status']='Ready for review';changed=True;ready+=1
        if changed:
            self.save();self.refresh()
            self.status.set(f'{ready} scheduled task(s) ready for manual review.')
        self.root.after(10000,self.tick)

    def refresh(self):
        for table in (self.account_table,self.group_table,self.task_table):
            for item in table.get_children():table.delete(item)
        for a in self.data['accounts']:
            proc=self.procs.get(a['id'])
            running=proc is not None and proc.poll() is None
            self.account_table.insert('', 'end', iid=a['id'], values=(a['name'],a['id'],'Running (tracked)' if running else 'Not tracked/running'))
        for g in self.data['groups']:
            self.group_table.insert('', 'end', iid=g['id'], values=(g['name'],g['keyword'],g['url']))
        for t in self.data['tasks']:
            self.task_table.insert('', 'end', iid=t['id'], values=(t['kind'].title(),t['account'],t['group'],t['due'].replace('T',' '),t['status']))
        previous=self.account_pick.get()
        choices=[a['id']+' | '+a['name'] for a in self.data['accounts']]
        self.account_pick['values']=choices
        self.account_pick.set(previous if previous in choices else (choices[0] if choices else ''))
        self.status.set(f"{len(self.data['accounts'])} accounts • {len(self.data['groups'])} groups • {len(self.data['tasks'])} review tasks • {ROOT}")

    def ask_ai(self):
        question=self.ai_prompt.get().strip()
        if not question:return
        model=self.model.get().strip() or 'llama3.2'
        context={'account_count':len(self.data['accounts']),'accounts':[{'id':a['id'],'name':a['name']} for a in self.data['accounts']], 'groups':[{'name':g['name'],'keyword':g['keyword']} for g in self.data['groups']][:100], 'task_statuses':[t['status'] for t in self.data['tasks']]}
        self.ai_output.delete('1.0','end');self.ai_output.insert('end','Contacting local Ollama...\n')
        def work():
            try:
                payload=json.dumps({'model':model,'stream':False,'messages':[{'role':'system','content':'You are a read-only assistant for a local account/group management tool. Answer using only provided data. Never claim to have taken actions. Data: '+json.dumps(context)},{'role':'user','content':question}]}).encode()
                req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=payload,headers={'Content-Type':'application/json'},method='POST')
                with urllib.request.urlopen(req,timeout=90) as response:
                    answer=json.load(response)['message']['content']
            except Exception as e:answer='Local Ollama unavailable: '+str(e)+'\nInstall Ollama and run: ollama pull '+model
            self.root.after(0,lambda:self.display_ai(answer))
        threading.Thread(target=work,daemon=True).start()

    def display_ai(self,answer):
        self.ai_output.delete('1.0','end');self.ai_output.insert('end',answer)

    def quit(self):
        self.save()
        self.temp_credentials.clear()
        self.root.destroy()

if __name__=='__main__':
    root=tk.Tk()
    ttk.Style().theme_use('clam')
    Manager(root)
    root.mainloop()
