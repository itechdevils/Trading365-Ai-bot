"""Local, allowlisted agent actions. No model-generated code execution."""
import re

def parse_command(text):
    s=text.lower().strip()
    m=re.search(r'(\d{1,3})\s*(?:new\s*)?(?:chrome\s*)?(?:profiles?|accounts?|phones?)',s)
    if m and any(x in s for x in ('create','banao','bnao','add')):
        return {'action':'create_profiles','count':int(m.group(1))}
    m=re.search(r'(?:phone|profile|account)\s*(?:number|no\.?|#)?\s*0*(\d{1,4})',s)
    if m and any(x in s for x in ('open','kholo','khol','launch')):
        return {'action':'open_profile','number':int(m.group(1))}
    if any(x in s for x in ('status','report','kitne','how many','summary')):
        return {'action':'status'}
    m=re.search(r'(?:groups?/)(\d{3,25})',s)
    if m and any(x in s for x in ('open','kholo','khol')):
        return {'action':'open_group','group_id':m.group(1)}
    return {'action':'unknown'}
