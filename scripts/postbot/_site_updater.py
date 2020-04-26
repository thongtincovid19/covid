#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import re
import requests
import json
import traceback
import github_utils as gitutils
import markdown_utils as mkutils
from time import localtime, strftime, gmtime
from datetime import datetime
date_format = "%Y-%m-%d"

import os.path
from os import path
# dirname = os.path.dirname(__file__)
dirname = "/home/ubuntu/covid19_repo"


json_gen_script = 'https://script.google.com/macros/s/AKfycbyOTr7VIG-a6yLJwIUSarxhcu37hlZTmWx4BF2PRxIYa2OiR0Xf/exec'
json_keys = {'title': "Title", 'content':'Content', 'source_label': 'Source', 'source_url': 'SourceLink', 'date': 'Date', 'tags': 'hashtags', 'translator': 'Translator', 'penname': 'PenName', 'status': 'Status'}

def getPost(title, content, src_lbl, src_url, date, category, tags):
    return f'---\nlayout: post\ntitle: {title}\ncategory: {category}\ntags: {tags}\n---\n{content}\n\nNguồn: [{src_lbl}]({src_url})'

def genPost(origin, repo):
    try:  
    
        # Get JSON data of sessions from google script:
        r = requests.get(json_gen_script)
        jData = json.loads(r.text)
        j = jData["post"]
    
        curDate = "2020-04-12"
        today = datetime.today().strftime(date_format)
        print(f"today = {today}")
        newsCnt = 0
        postDir =  os.path.join(dirname, 'thongtincovid19.github.io/_posts')
        print(postDir)
        for p in j:
            newsCnt += 1
            title = f"\"{p[json_keys['title']].strip()}\""
            content = mkutils.markdownAsserter(p[json_keys['content']].strip())
            src_lbl = p[json_keys['source_label']]
            src_url = p[json_keys['source_url']]
            date = p[json_keys['date']]
            tags = p[json_keys['tags']]
            if not tags:
                tags = 'null'
            else:
                tags_arr = tags.split(",")
                tags = ""
                for t in tags_arr:
                    tags += f"\n  - {t.strip()}"
            if date != curDate:
                curDate = date
                newsCnt = 1
                
            penname = p[json_keys['penname']]
            status = p[json_keys['status']]
            fname = f"{curDate}-news{newsCnt}.md"
            absFname = os.path.join(postDir,fname)
            if status == "Review Done":
                # print(getPost(title, content, src_lbl, src_url, date, category="news", tags=tags))
                print(fname)
                branch_name = fname
                gitutils.github_checkout(origin, repo, branch_name=branch_name)
                with open(absFname, 'wt', encoding='utf-8') as f:
                    f.write(getPost(title, content, src_lbl, src_url, date, category="news", tags=tags))
                changed = [ item.a_path for item in repo.index.diff(None) ]
                pull_request_branch = None
                if len(changed) > 0:
                    # print(repo.untracked_files)
                    # repo.git.add(repo.untracked_files)
                    for uf in changed:
                        head, tail = os.path.split(uf)
                        gitutils.github_add_commit_push_pullrequest(origin, repo, uf, tail, tail)
                        pull_request_branch = branch_name
                
                if len(repo.untracked_files) > 0:
                    print(repo.untracked_files)
                    # repo.git.add(repo.untracked_files)
                    for uf in repo.untracked_files:
                        head, tail = os.path.split(uf)
                        gitutils.github_add_commit_push_pullrequest(origin, repo, uf, tail, tail)
                        pull_request_branch = branch_name
                
                repo.git.checkout("-f", "master")
                
                if not pull_request_branch:
                    # delete not pushed branch
                    repo.git.branch("-D", branch_name)
            # elif curDate <= "2020-04-24":
            #     print(f"Skip: {curDate}")
            else:
                print(f"Skip: {fname}")
                
    
    # except ValueError:
    #  send_email.send_email(user,password,addr,"ValueError:may be YYYY/MM")
    except Exception as e:
        #send_email.send_email(user,password,addr,"Something is Wrong")
        print ('something is wrong')
        # print(e)
        traceback.print_exc()
    
def run():
    now = datetime.now()
    print("in siteupdter running")
    # dirname = "/var/www/covid19"
    git_dir = os.path.join(dirname, 'thongtincovid19.github.io')
    repo = gitutils.Repo(git_dir)
    
    # current = repo.head.commit
    # print(f"repo.head.commit: {current}")
    
    origin = repo.remote(name='origin')
    
    repo.remotes.origin.fetch()
    origin.pull()
    # repo.git.pull(origin, "master")
    
    # newcur = repo.head.commit
    genPost(origin, repo)
    
    return "OK"
    
def run1():
    print("in dir postbot")
    print(os.path.abspath("/home/ubuntu/covid19_repo"))
    print(dirname)
    
    return "OK"
        
if __name__ == "__main__":
    run()