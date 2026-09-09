def resolve(source, context):
    object_id = context.get('exampleObject')
    if not isinstance(object_id, str) or not object_id: return []
    return [{'kind':'object', 'key':'example:object:' + object_id, 'title':'Object ' + object_id}]
