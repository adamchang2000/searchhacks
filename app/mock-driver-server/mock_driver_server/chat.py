import json
import os
import urllib.error
import urllib.request
from django.http import JsonResponse
from ninja import Router, Body
import asyncio
import queue
import threading
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
_progress = threading.local()
def emit(event, **data):
    sink = getattr(_progress, "sink", None)
    if sink: sink.put({"event":event, **data})
router = Router()
AVAILABLE_PROVIDERS = os.environ.get("SEARCH_PROVIDERS", "exa,brave,parallel").split(",")
OPTIMIZER_URL = os.environ.get("OPTIMIZER_URL", "https://optimizer.int.exe.xyz")
TELEM_URL = os.environ.get("TELEM_BASE_URL", "https://hack.telem.ai/api")
def post_json(url, payload, headers=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type":"application/json", **(headers or {})}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        detail=e.read().decode(errors="replace")
        raise RuntimeError(f"Upstream returned HTTP {e.code}: {detail[:500]}") from e
@router.post("/search")
def chat_search(request, payload: dict = Body(...)):
    query=str(payload.get("query","")).strip()
    if not query or len(query)>1000:
        return JsonResponse({"error":"Enter a query between 1 and 1000 characters."}, status=400)
    key=os.environ.get("TELEM_API_KEY")
    if not key:
        return JsonResponse({"error":"Telem is not configured on the server."}, status=503)
    try:
        emit("routing", query=query)
        choice=post_json(OPTIMIZER_URL+"/api/which_search", {"query":query,"available_providers":AVAILABLE_PROVIDERS})
        emit("searching", query=query, provider=choice["provider"])
        result=post_json(TELEM_URL+"/v1/search", {"user_input":{"query":query},"search":{"providers":{"include":[choice["provider"]]},"num_results":5},"metadata":{"source":"searchhacks-chatbot","optimizer_provider":choice["provider"]}}, {"Authorization":"Bearer "+key})
        normalized=[]
        for run in result.get("preprocessor_runs",[]):
            output=run.get("output_payload") or {}
            items=output.get("results") or output.get("organic") or []
            for item in items:
                normalized.append({"title":item.get("title") or item.get("name") or item.get("url") or "Search result","url":item.get("url") or item.get("link") or "","snippet":item.get("snippet") or item.get("description") or item.get("content") or ""})
        emit("results", query=query, provider=choice["provider"], results=normalized[:10], feedback_token=choice["feedback_token"])
        return JsonResponse({"feedback_token":choice["feedback_token"],"provider":choice["provider"],"results":normalized[:10],"telem":{"session_id":result.get("session_id"),"interaction_id":result.get("interaction_id"),"status":result.get("status"),"response_keys":list(result.keys())}})
    except Exception as e:
        return JsonResponse({"error":str(e)},status=502)
def chat_feedback(request, payload: dict = Body(...)):
    try:
        return post_json(OPTIMIZER_URL+"/api/submit_feedback", {"feedback_token":payload.get("feedback_token"),"feedback":payload.get("feedback", {})})
    except Exception as e:
        return JsonResponse({"error":str(e)},status=502)

# Model conversations are stored server-side; clients receive only an opaque session ID.
import sqlite3
import uuid
from pathlib import Path
SYSTEM_PROMPT = """You are a concise web research assistant. Use search for web sources.
Each search asks the optimizer which provider to use; Telem executes only that provider.
Do not choose providers or repeat a query to compare providers. Search again only when a
distinct query is needed to answer the user.
After answering, WAIT for the user's next response before assessing search outcomes.
Call search_feedback for a previous search only when the subsequent user response provides
evidence for one or more optional outcome fields in a feedback object:
purchase_conversion: whether the user purchased;
user_confirmed_outcome: whether the user explicitly confirms reaching their goal;
user_stopped_following_up: whether follow-ups stopped after more than one search query.
Only supply observed booleans. Omit unknown fields; never turn absence of evidence into false.
You cannot infer that follow-ups stopped merely from silence. This requires explicit evidence
and more than one prior search. Later calls can update individual observed fields.
Include evidence grounded in the user's response. Relevant-looking results alone are not an
outcome. Silence, unrelated replies, and ambiguous follow-ups are insufficient: leave pending.
Never grade a search created in the current turn. Cite source URLs. Never invent outcomes."""
TOOLS = [
 {"type":"function","function":{"name":"search","description":"Search using the optimizer-selected provider through Telem.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
 {"type":"function","function":{"name":"search_feedback","description":"Grade a prior-turn search outcome based on the subsequent user response; never grade current-turn searches.","parameters":{"type":"object","properties":{"feedback_token":{"type":"string"},"feedback":{"type":"object","properties":{"purchase_conversion":{"type":"boolean"},"user_confirmed_outcome":{"type":"boolean"},"user_stopped_following_up":{"type":"boolean"}},"additionalProperties":False,"minProperties":1},"evidence":{"type":"string"}},"required":["feedback_token","feedback","evidence"]}}}
]
def chat_db():
    db=sqlite3.connect(Path(__file__).resolve().parents[1]/"chat.sqlite3",timeout=30)
    db.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, messages TEXT NOT NULL)")
    if "updated_at" not in {row[1] for row in db.execute("PRAGMA table_info(conversations)")}:
        db.execute("ALTER TABLE conversations ADD COLUMN updated_at TEXT")
    return db

@router.post("/message")
def chat_message(request, payload: dict = Body(...)):
    query=str(payload.get("query","")).strip()
    if not query or len(query)>4000:
        return JsonResponse({"error":"Enter a message between 1 and 4000 characters."},status=400)
    sid=str(payload.get("session_id") or uuid.uuid4())
    try:
        uuid.UUID(sid)
        with chat_db() as db:
            row=db.execute("SELECT messages FROM conversations WHERE id=?",(sid,)).fetchone()
        messages=json.loads(row[0]) if row else [{"role":"system","content":SYSTEM_PROMPT}]
        messages[0]={"role":"system","content":SYSTEM_PROMPT}
        messages.append({"role":"user","content":query})
        traces=[]
        feedback=[]
        allowed_tokens=set()
        for msg in messages:
            if msg.get("role")=="tool":
                try:
                    token=json.loads(msg.get("content","{}")).get("feedback_token")
                    if token and "results" in json.loads(msg["content"]): allowed_tokens.add(token)
                except (ValueError,AttributeError): pass
        for _ in range(12):
            emit("model", message="Preparing answer" if traces else "Reviewing conversation")
            response=post_json(os.environ.get("LLM_BASE_URL","https://llm.int.exe.xyz/v1")+"/chat/completions",
                {"model":os.environ.get("LLM_MODEL","router/auto"),"messages":messages,"tools":TOOLS if allowed_tokens else TOOLS[:1],"max_tokens":2200})
            answer=response["choices"][0]["message"]
            answer={k:v for k,v in answer.items() if k in ("role","content","tool_calls")}
            messages.append(answer)
            calls=answer.get("tool_calls") or []
            if not calls:
                with chat_db() as db:
                    db.execute("INSERT OR REPLACE INTO conversations (id,messages,updated_at) VALUES (?,?,strftime(\'%Y-%m-%dT%H:%M:%fZ\',\'now\'))",(sid,json.dumps(messages)))
                return {"session_id":sid,"answer":answer.get("content") or "No answer returned.","searches":traces,"feedback":feedback}
            for call in calls:
                name=call["function"]["name"]
                try:
                    args=json.loads(call["function"]["arguments"])
                    if name=="search":
                        result=chat_search(request,args)
                        if isinstance(result,JsonResponse):
                            if result.status_code!=200: raise RuntimeError(json.loads(result.content).get("error","Search failed"))
                            result=json.loads(result.content)
                        traces.append(result)
                    elif name=="search_feedback":
                        if args.get("feedback_token") not in allowed_tokens: raise ValueError("Only prior-turn searches can receive feedback.")
                        if not str(args.get("evidence","")).strip(): raise ValueError("User outcome evidence required.")
                        record=args.get("feedback")
                        if not isinstance(record,dict) or not record or any(k not in ("purchase_conversion","user_confirmed_outcome","user_stopped_following_up") or type(v) is not bool for k,v in record.items()): raise ValueError("Supply observed boolean feedback fields")
                        if "user_stopped_following_up" in record and len(allowed_tokens) <= 1: raise ValueError("Stopped-following-up requires more than one prior search")
                        emit("feedback_submitting", **args)
                        result=chat_feedback(request,args)
                        if isinstance(result,JsonResponse): raise RuntimeError("Feedback submission failed")
                        emit("feedback_submitted", **args)
                        feedback.append({"feedback_token":args["feedback_token"],"feedback":args["feedback"],"evidence":args["evidence"]})
                    else: raise ValueError("Unknown tool")
                except Exception as e:
                    emit("tool_error", tool=name, message=str(e))
                    result={"error":str(e)}
                messages.append({"role":"tool","tool_call_id":call["id"],"content":json.dumps(result)})
        return JsonResponse({"error":"Model exceeded the tool-call limit."},status=502)
    except Exception as e:
        return JsonResponse({"error":str(e)},status=502)


@csrf_exempt
async def chat_stream(request):
    if request.method != "POST":
        return JsonResponse({"error":"POST required"}, status=405)
    try:
        payload=json.loads(request.body)
        if not isinstance(payload,dict): raise ValueError()
    except (ValueError,TypeError):
        return JsonResponse({"error":"Invalid JSON body"},status=400)
    events=queue.Queue()
    def run():
        _progress.sink=events
        try:
            result=chat_message(request,payload)
            if isinstance(result,JsonResponse):
                events.put({"event":"error", **json.loads(result.content)})
            else:
                events.put({"event":"done", **result})
        except Exception as e:
            events.put({"event":"error","error":str(e)})
        finally:
            _progress.sink=None
            events.put(None)
    threading.Thread(target=run,daemon=True).start()
    async def stream():
        yield json.dumps({"event":"started","message":"Reviewing conversation"})+"\n"
        while True:
            item=await asyncio.to_thread(events.get)
            if item is None: break
            yield json.dumps(item)+"\n"
    response=StreamingHttpResponse(stream(),content_type="application/x-ndjson")
    response["Cache-Control"]="no-cache, no-transform"
    response["X-Accel-Buffering"]="no"
    return response


@router.get("/conversations")
def conversations(request):
    with chat_db() as db:
        rows=db.execute("SELECT id,messages,updated_at FROM conversations ORDER BY COALESCE(updated_at,'') DESC,rowid DESC").fetchall()
    result=[]
    for sid,raw,updated in rows:
        messages=json.loads(raw)
        users=[m for m in messages if m.get("role")=="user"]
        result.append({"id":sid,"title":str(users[0].get("content","New chat"))[:90] if users else "New chat","message_count":len(users),"updated_at":updated})
    return result

@router.get("/conversations/{session_id}")
def conversation(request, session_id: str):
    with chat_db() as db:
        row=db.execute("SELECT messages FROM conversations WHERE id=?",(session_id,)).fetchone()
    if row is None:
        return JsonResponse({"error":"Chat not found"},status=404)
    return {"session_id":session_id,"messages":[m for m in json.loads(row[0]) if m.get("role")!="system"]}
