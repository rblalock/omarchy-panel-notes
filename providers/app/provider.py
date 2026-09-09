def resolve(source, context):
    app = source["app"]
    return [{"kind": "app", "key": "app:" + app, "title": app, "label":"App"}]
