from ninja import Router, Schema

router = Router()

class HealthResponse(Schema):
    status: str

@router.get("", response=HealthResponse)
def health(request):
    return {"status": "ok"}
