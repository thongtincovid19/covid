from git import Repo #GitPython

from github import Github #PyGithub

def github_pull_request(branch_name, title = "Daily Post Policy"):
    # g = Github("cf033246877d7e44586074282688c7803129092c") #token tatungbot
    g = Github("f31bd948bd1479619d15c5cf8f830fa557eef382") #token tatung
    covidrepo = g.get_repo("thongtincovid19/thongtincovid19.github.io")
    print(covidrepo.name)
    body = "New daily post"
    try:
        pr = covidrepo.create_pull(title=title, body=body, head=branch_name, base="master")
        print(f"hey---: {pr}")
    except Exception as e:
        print(f"my exception: {e}")
        if "A pull request already exists" in f"{e}":
            return "OK"
        else:
            return "Exception"
    return "OK"
    
def github_checkout(origin, repo, branch_name):
    try:
        repo.git.checkout("-b", branch_name)
    except Exception as e:
        if "A branch named" in f"{e}" and "already exists" in f"{e}":
            print(f"branch exists: {branch_name}")
            repo.git.checkout(branch_name)
        else:
            print("------- in checkout")
            traceback.print_exc()

def github_add_commit_push_pullrequest(origin, repo, file, title, commit_mgs = 'new posts'):
    branch_name = title
    
    repo.git.add(file)
    repo.index.commit(commit_mgs)
    origin.push(branch_name)
    github_pull_request(branch_name, title)