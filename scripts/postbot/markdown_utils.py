import re

def markdownAsserter(content):
    content = newlineAsserter(content)
    return content
    
def newlineAsserter(content):
    content = re.sub(r'\n+', '\n', content)
    content = content.replace('  ', "")
    content = content.replace('\n', "\n\n")
    return content