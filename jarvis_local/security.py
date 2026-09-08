from dataclasses import dataclass

READ_ONLY={"system.status","file.list","file.read","file.search","browser.open","web.search"}
LOW_RISK={"app.open","folder.open","file.create","file.rename","file.move","media.control","note.write"}
CONFIRM={"file.delete","system.shutdown","system.restart","settings.change","message.send","command.run"}

@dataclass(frozen=True)
class Permission:
    tool:str
    level:str

def permission_for(tool):
    if tool in READ_ONLY: return Permission(tool,"read")
    if tool in LOW_RISK: return Permission(tool,"low")
    return Permission(tool,"confirm")

def validate(tool,args):
    if not isinstance(tool,str) or not tool or len(tool)>80: raise ValueError("Invalid tool name")
    if not isinstance(args,dict): raise ValueError("Tool arguments must be an object")
