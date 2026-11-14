from ninja import Router

health_router = Router()

@health_router.get("")
def health(request):
    return {"status": "ok"}
