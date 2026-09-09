import json
import unicodedata
import uuid


def resolve(source, context):
    name = context.get("name", "")
    if not isinstance(name, str) or not name.strip(): return []
    name = unicodedata.normalize("NFC", name.strip())
    identity = json.dumps([source["app"], name.casefold()], ensure_ascii=False)
    return [{"kind":"named", "key":"named:" + uuid.uuid5(uuid.NAMESPACE_URL, identity).hex,
             "app":source["app"], "title":name, "label":name}]
