import aiocache
import typing
import fastapi
import aiocache.serializers
from hypnosis_utils.logger import getLogger
from ..repository import comparator_dict as comparator_dict_repository

LOGGER = getLogger("v1.maker.services.comparator")


@aiocache.cached_stampede(
    cache=aiocache.SimpleMemoryCache,
    lease=2, # seconds to lock the call to avoid stampede
    ttl=60, # seconds to cache the result
    namespace="hypnosis-maker",
    serializer=aiocache.serializers.NullSerializer(), # We want to save the pydantic model as is
    noself=False,
)
async def getComparatorAlternativeDictFromDatabase(
    language: str = "es"
) -> comparator_dict_repository.ComparatorAlternativeDict:
    LOGGER.info("[MAKER] Fetching comparator alternative dictionary from the database...")
    allDicts = await comparator_dict_repository.MAKER_REPOSITORY_INSTANCE.getAlternativeDicts(
        query={
            "language": language
        }
    )
    
    if len(allDicts) == 0:
        LOGGER.warning("[MAKER] No comparator alternative dictionary found.")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_204_NO_CONTENT,
            detail="No comparator alternative dictionary found for maker."
        )
    
    if len(allDicts) > 1:
        LOGGER.warning(f"[MAKER] More than one comparator alternative dictionary found (len {len(allDicts)}), returning the first one.")

    toReturn = allDicts[0]

    return toReturn

async def createComparatorAlternativeDict(
    alternativeDict : comparator_dict_repository.ComparatorAlternativeDict,
):
    LOGGER.info("[MAKER] Creating comparator alternative dictionary...")
    await comparator_dict_repository.MAKER_REPOSITORY_INSTANCE.createAlternativeDict(alternativeDict)


# ? TYPES

getComparatorAlternativeDict = typing.cast(
    typing.Callable[[str], comparator_dict_repository.ComparatorAlternativeDict],
    getComparatorAlternativeDictFromDatabase
)