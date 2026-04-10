"""API router for Historical Echoes — semantic similarity matches."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/for-prediction/{prediction_id}")
def get_echoes(prediction_id: int, timeframe: str = "t7", limit: int = 5):
    """Get historical echo matches for a prediction.

    Args:
        prediction_id: The prediction to find echoes for.
        timeframe: Outcome timeframe to aggregate (t1, t3, t7, t30).
        limit: Max number of similar posts to return.
    """
    from shit.echoes.echo_service import EchoService

    service = EchoService()
    embedding = service.get_embedding(prediction_id)
    if embedding is None:
        raise HTTPException(404, "No embedding found for this prediction")

    matches = service.find_similar_posts(
        embedding=embedding,
        limit=limit,
        exclude_prediction_id=prediction_id,
    )
    return service.aggregate_echoes(matches, timeframe=timeframe)
