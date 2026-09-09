"""One bounded provider invocation. Isolation is lifecycle control, not a sandbox."""
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location('context_provider', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
request = json.load(sys.stdin)
print(json.dumps(module.resolve(request['source'], request['context'])))
