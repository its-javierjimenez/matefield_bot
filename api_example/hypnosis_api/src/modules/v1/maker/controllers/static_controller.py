import typing
import fastapi
import hashlib
from hypnosis_utils.logger import getLogger
from src.modules.v1.shared.services import assets_service



LOGGER = getLogger("v1.maker.controllers.static")



ROUTER = fastapi.APIRouter(
    prefix="/static",
    tags=["static"],
)



# ? POST y no get, porque al poner un texto con acentos y caracteres especiales,
# ? si lo lego a pasar por Header puede tener problemas de decoding y encoding,
# ? entonces usamos el body.
# ? tampoco pasamos el texto por query o path, puesto que el texto contiene espacios
# ? podriamos usar GET para obtenerlo por hash, ya que no tiene espacios
# ? pero prefiero mantener los dos endpoints iguales.
# ? https://stackoverflow.com/questions/73234675/how-to-download-a-file-after-posting-data-using-fastapi/73240097#73240097
# ? Ahí explican el porque usar attachment que es para descargar, y no inline que es para mostrar en browser.
# ? cuando se recibe un stream por post, y al usar inline o no poner los headers, se recibe un 405 not allowed y el navegador
# ? intenta usar get.
# ? al fin y al cabo queremos descargar, no mostrarlo en una UI, jeje
@ROUTER.post(
    "/audio/byText",
    tags=["assets"],
    description="Retrieve static audio based on provided text.",
    response_class=fastapi.responses.StreamingResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "content": {"audio/mpeg": {}},
            "description": "Audio file retrieved successfully."
        },
        fastapi.status.HTTP_404_NOT_FOUND: {"description": "File not found"},
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Invalid input"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"}
    }
)
async def getStaticAudioByText(
    text : typing.Annotated[str, fastapi.Body(media_type="text/plain")],
) -> fastapi.responses.StreamingResponse:
    LOGGER.info(f"[MAKER] Request received for static audio retrieval with text: {text}")

    hashedText = hashlib.sha256(text.encode()).hexdigest()

    await assets_service.checkMakerStaticAudioExists(
        hashedText=hashedText
    )

    audioIter = await assets_service.getMakerStaticAudio(hashedText=hashedText)

    return fastapi.responses.StreamingResponse(
        content=audioIter[0], status_code=fastapi.status.HTTP_200_OK, media_type="audio/mpeg",
        headers={"content-type": "audio/mpeg" , "Content-Disposition": f"attachment; filename={hashedText}.mp3"},
        background=fastapi.BackgroundTasks([audioIter[1].aclose])
    )



@ROUTER.post(
    "/audio/byHash",
    tags=["assets"],
    description="Retrieve static audio based on provided hash.",
    response_class=fastapi.responses.StreamingResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "content": {"audio/mpeg": {}},
            "description": "Audio file retrieved successfully."
        },
        fastapi.status.HTTP_404_NOT_FOUND: {"description": "File not found"},
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Invalid input"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"}
    }
)
async def getStaticAudioByHash(
    hashedText: typing.Annotated[str, fastapi.Body(media_type="text/plain")],
) -> fastapi.responses.StreamingResponse:
    LOGGER.info(f"[MAKER] Request received for static audio retrieval with hash: {hashedText}")

    await assets_service.checkMakerStaticAudioExists(
        hashedText=hashedText
    )

    audioIter = await assets_service.getMakerStaticAudio(hashedText=hashedText)

    return fastapi.responses.StreamingResponse(
        content=audioIter[0], status_code=fastapi.status.HTTP_200_OK, media_type="audio/mpeg",
        headers={"content-type": "audio/mpeg" , "Content-Disposition": f"attachment; filename={hashedText}.mp3"},
        background=fastapi.BackgroundTasks([audioIter[1].aclose])
    )



@ROUTER.put(
    "/audio",
    tags=["assets"],
    description="Store static audio based on provided text.",
    response_class=fastapi.responses.JSONResponse,
    responses={
        fastapi.status.HTTP_201_CREATED: {
            "description": "Audio file stored successfully."
        },
        fastapi.status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid input."
        },
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error."
        }
    }
)
async def storeStaticAudio(
    text: typing.Annotated[str, fastapi.Form(media_type="text/plain")],
    audio: typing.Annotated[fastapi.UploadFile, fastapi.File(media_type="audio/mpeg")],
) -> fastapi.responses.JSONResponse:
    LOGGER.info(f"[MAKER] Request received for static audio storage with text: {text}")

    hashedText = hashlib.sha256(text.encode()).hexdigest()

    await assets_service.submitMakerStaticAudio(
        audioFile=audio,
        hashedText=hashedText,
        privacy="private"
    )

    
    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_201_CREATED,
        content={
            "message": f"File {hashedText}.mp3 uploaded successfully.",
            "fileName": f"{hashedText}.mp3",
            "contentType": audio.content_type,
            "path": f"maker/static_audios/{hashedText}.mp3"
        }
    )
