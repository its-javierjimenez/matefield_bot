import typing
import fastapi
import httpx
from hypnosis_utils.logger import getLogger
from src.config import ENVIRONMENT_SETTINGS
from src.modules.v1.shared.services import mental_storage_service


LOGGER = getLogger("v1.shared.service.assets")

# MARK: Path Generators


@typing.overload
def getMakerZipPath(
    userID: str,
    taskID: str,
    separated: typing.Literal[True]
) -> tuple[str, str]:
    ...

@typing.overload
def getMakerZipPath(
    userID: str,
    taskID: str,
    separated: typing.Literal[False] = False
) -> str:
    ...

def getMakerZipPath(
    userID: str,
    taskID: str,
    separated: typing.Literal[True, False] = False
) -> str | tuple[str, str]:
    """
    Function to get the folder where the maker module saves the audio zips.

    returns:
        str: The path where the audio zips are saved. (with {userID} and {taskID} placeholders)
        tuple[str, str]: A tuple with the folder path and the zip file name.
    """
    
    if separated:
        return (
            f"{ENVIRONMENT_SETTINGS.MAKER_SETTINGS.MAKER_ZIPS_FOLDER}/{userID}",
            f"{taskID}.zip"
        )
    
    return f"{ENVIRONMENT_SETTINGS.MAKER_SETTINGS.MAKER_ZIPS_FOLDER}/{userID}/{taskID}.zip"


@typing.overload
def getExportAudioPath(
    userID: str,
    taskID: str,
    separated: typing.Literal[True]
) -> tuple[str, str]:
    ...

@typing.overload
def getExportAudioPath(
    userID: str,
    taskID: str,
    separated: typing.Literal[False] = False
) -> str:
    ...

def getExportAudioPath(
    userID: str,
    taskID: str,
    separated: typing.Literal[True, False] = False
) -> str | tuple[str, str]:
    """
    Function to get the folder where the export module saves the final audios.

    returns:
        str: The path where the final audios are saved. (with {userID} and {taskID} placeholders)
        tuple[str, str]: A tuple with the folder path and the audio file name.
    """
    
    if separated:
        return (
            f"{ENVIRONMENT_SETTINGS.EXPORT_SETTINGS.EXPORT_AUDIOS_FOLDER}/{userID}/{taskID}",
            "audio.mp3"
        )
    
    return f"{ENVIRONMENT_SETTINGS.EXPORT_SETTINGS.EXPORT_AUDIOS_FOLDER}/{userID}/{taskID}/audio.mp3"


@typing.overload
def getExportTemplatePath(
    filename: str,
    separated: typing.Literal[True]
) -> tuple[str, str]:
    ...

@typing.overload
def getExportTemplatePath(
    filename: str,
    separated: typing.Literal[False] = False
) -> str:
    ...

def getExportTemplatePath(
    filename: str,
    separated: typing.Literal[True, False] = False
) -> str | tuple[str, str]:
    """
    Function to get the folder where the export module saves the audio templates.

    returns:
        str: The path where the audio templates are saved. (with {userID} and {taskID} placeholders)
        tuple[str, str]: A tuple with the folder path and the template file name.
    """

    if separated:
        return (
            ENVIRONMENT_SETTINGS.EXPORT_SETTINGS.EXPORT_TEMPLATES_FOLDER,
            filename
        )

    return f"{ENVIRONMENT_SETTINGS.EXPORT_SETTINGS.EXPORT_TEMPLATES_FOLDER}/{filename}"



@typing.overload
def getMakerStaticAudioPath(
    hashedText: str,
    separated: typing.Literal[True]
) -> tuple[str, str]:
    ...

@typing.overload
def getMakerStaticAudioPath(
    hashedText: str,
    separated: typing.Literal[False] = False
) -> str:
    ...

def getMakerStaticAudioPath(
    hashedText: str,
    separated: typing.Literal[True, False] = False
) -> str | tuple[str, str]:
    """
    Get the path where the maker module saves the static audios.

    args:
        hashedText: The hashed text (SHA256) used as filename.
        separated: If True, returns a tuple with (folder, filename).

    returns:
        str: The full path where the static audios are saved.
        tuple[str, str]: A tuple with the folder path and the audio file name.
    """
    
    if separated:
        return (
            ENVIRONMENT_SETTINGS.MAKER_SETTINGS.MAKER_STATIC_AUDIOS_FOLDER,
            f"{hashedText}.mp3"
        )
    
    return f"{ENVIRONMENT_SETTINGS.MAKER_SETTINGS.MAKER_STATIC_AUDIOS_FOLDER}/{hashedText}.mp3"



# MARK: Checking Operations



async def checkMakerZipExists(
    userID: str,
    taskID: str,
) -> bool:
    """
    Check if a maker zip file exists in storage.

    args:
        userID: The user ID associated with the task.
        taskID: The task ID associated with the zip file.
    
    raises:
        fastapi.HTTPException: If the file does not exist in storage.
    """
    
    path = getMakerZipPath(userID=userID, taskID=taskID, separated=False)
    
    LOGGER.info(f"[ASSETS] Checking if maker zip exists at path: {path}")
    
    return await mental_storage_service.checkIfFileInStorage(path=path)



async def checkExportAudioExists(
    userID: str,
    taskID: str,
) -> bool:
    """
    Check if an export audio file exists in storage.

    args:
        userID: The user ID associated with the task.
        taskID: The task ID associated with the audio file.
    
    raises:
        fastapi.HTTPException: If the file does not exist in storage.
    """
    
    path = getExportAudioPath(userID=userID, taskID=taskID, separated=False)
    
    LOGGER.info(f"[ASSETS] Checking if export audio exists at path: {path}")
    
    return await mental_storage_service.checkIfFileInStorage(path=path)



async def checkExportTemplateExists(
    filename: str,
) -> bool:
    """
    Check if an export template file exists in storage.

    args:
        filename: The template file name.
    
    raises:
        fastapi.HTTPException: If the file does not exist in storage.
    """
    
    path = getExportTemplatePath(filename=filename, separated=False)
    
    LOGGER.info(f"[ASSETS] Checking if export template exists at path: {path}")
    
    return await mental_storage_service.checkIfFileInStorage(path=path)



async def checkAssetExists(
    path: str,
) -> bool:
    """
    Check if an asset exists in storage using a custom path.

    args:
        path: The full path to the file in storage.
    
    raises:
        fastapi.HTTPException: If the file does not exist in storage.
    """
    
    LOGGER.info(f"[ASSETS] Checking if asset exists at path: {path}")
    
    return await mental_storage_service.checkIfFileInStorage(path=path)



async def checkMakerStaticAudioExists(
    hashedText: str,
) -> bool:
    """
    Check if a maker static audio file exists in storage.

    args:
        hashedText: The hashed text (SHA256) used as filename.
    
    raises:
        fastapi.HTTPException: If the file does not exist in storage.
    """
    
    path = getMakerStaticAudioPath(hashedText=hashedText, separated=False)
    
    LOGGER.info(f"[ASSETS] Checking if maker static audio exists at path: {path}")
    
    return await mental_storage_service.checkIfFileInStorage(path=path)




# MARK: Submission Operations



async def _submitFileToStorage(
    file: fastapi.UploadFile,
    folder: str,
    filename: str,
    privacy: str,
    contentType: str | None = None
) -> str:
    """
    Internal helper to submit a file to storage.
    
    args:
        file: The file to upload.
        folder: The folder path in storage.
        filename: The filename in storage.
        privacy: The privacy level ("public" or "private").
        contentType: Optional content type override.
        
    returns:
        str: The full path where the file was saved.
        
    raises:
        fastapi.HTTPException: If the file cannot be uploaded.
    """
    async def asyncGenerator():
        await file.seek(0)
        while chunk := await file.read():
            yield chunk
    
    await mental_storage_service.submitFileToStorageAsStream(
        asyncGenerator=asyncGenerator(),
        fileName=filename,
        folderName=folder,
        privacy=privacy,
        contentType=contentType or file.content_type or "application/octet-stream",
    )

    if not await mental_storage_service.checkIfFileInStorage(
        path=f"{folder}/{filename}",
        checkSize=True
    ):
        raise fastapi.HTTPException(status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"File upload failed for unknown reasons. It can be: 0-byte file or storage service issue. Path: '{folder}/{filename}' Content-Type: '{contentType}'")

    return f"{folder}/{filename}"



async def submitMakerZip(
    zipFile: fastapi.UploadFile,
    userID: str,
    taskID: str,
    privacy: str = "private"
) -> str:
    """
    Submit a maker zip file to storage.

    args:
        zipFile: The zip file to upload.
        userID: The user ID associated with the task.
        taskID: The task ID associated with the zip file.
        privacy: The privacy level of the file. Defaults to "private".

    returns:
        str: The full path where the zip was saved.
    
    raises:
        fastapi.HTTPException: If the file cannot be uploaded to storage.
    """
    
    folder, filename = getMakerZipPath(userID=userID, taskID=taskID, separated=True)
    
    LOGGER.info(f"[ASSETS] Submitting maker zip file to storage at '{folder}/{filename}'")

    return await _submitFileToStorage(
        file=zipFile,
        folder=folder,
        filename=filename,
        privacy=privacy,
        contentType=zipFile.content_type or "application/zip",
    )



async def submitExportAudio(
    audioFile: fastapi.UploadFile,
    userID: str,
    taskID: str,
    privacy: str = "public"
) -> str:
    """
    Submit an export audio file to storage.

    args:
        audioFile: The audio file to upload.
        userID: The user ID associated with the task.
        taskID: The task ID associated with the audio file.
        privacy: The privacy level of the file. Defaults to "public".

    returns:
        str: The full path where the audio was saved.
    
    raises:
        fastapi.HTTPException: If the file cannot be uploaded to storage.
    """
    
    folder, filename = getExportAudioPath(userID=userID, taskID=taskID, separated=True)
    
    LOGGER.info(f"[ASSETS] Submitting export audio file to storage at '{folder}/{filename}'")

    return await _submitFileToStorage(
        file=audioFile,
        folder=folder,
        filename=filename,
        privacy=privacy,
        contentType=audioFile.content_type or "audio/mpeg",
    )



async def submitExportTemplate(
    templateFile: fastapi.UploadFile,
    filename: str,
    privacy: str = "private"
) -> str:
    """
    Submit an export template file to storage.

    args:
        templateFile: The template file to upload.
        filename: The name to give to the file in storage.
        privacy: The privacy level of the file. Defaults to "private".

    returns:
        str: The full path where the template was saved.
    
    raises:
        fastapi.HTTPException: If the file cannot be uploaded to storage.
    """
    
    folder, _ = getExportTemplatePath(filename=filename, separated=True)
    
    LOGGER.info(f"[ASSETS] Submitting export template file to storage at '{folder}/{filename}'")

    return await _submitFileToStorage(
        file=templateFile,
        folder=folder,
        filename=filename,
        privacy=privacy,
        contentType=templateFile.content_type or "audio/mpeg",
    )



async def submitMakerStaticAudio(
    audioFile: fastapi.UploadFile,
    hashedText: str,
    privacy: str = "private"
) -> str:
    """
    Submit a maker static audio file to storage.

    args:
        audioFile: The audio file to upload.
        hashedText: The hashed text (SHA256) to use as filename.
        privacy: The privacy level of the file. Defaults to "private".

    returns:
        str: The full path where the audio was saved.
    
    raises:
        fastapi.HTTPException: If the file cannot be uploaded to storage.
    """
    
    folder, filename = getMakerStaticAudioPath(hashedText=hashedText, separated=True)
    
    LOGGER.info(f"[ASSETS] Submitting maker static audio file to storage at '{folder}/{filename}'")

    return await _submitFileToStorage(
        file=audioFile,
        folder=folder,
        filename=filename,
        privacy=privacy,
        contentType=audioFile.content_type or "audio/mpeg",
    )



# MARK: Retrieval Operations



async def getMakerZip(
    userID: str,
    taskID: str,
) -> tuple[typing.AsyncGenerator[bytes, None], httpx.Response]:
    """
    Get a maker zip file from storage as a stream.

    args:
        userID: The user ID associated with the task.
        taskID: The task ID associated with the zip file.

    returns:
        tuple: A tuple containing the async generator and the response object.
    
    raises:
        fastapi.HTTPException: If the file cannot be retrieved from storage.
    """
    
    path = getMakerZipPath(userID=userID, taskID=taskID, separated=False)
    
    LOGGER.info(f"[ASSETS] Getting maker zip from storage at path: {path}")

    return await mental_storage_service.getFileFromStorageStream(
        path=path,
        mediaType="application/zip"
    )



async def getExportAudio(
    userID: str,
    taskID: str,
) -> tuple[typing.AsyncGenerator[bytes, None], httpx.Response]:
    """
    Get an export audio file from storage as a stream.

    args:
        userID: The user ID associated with the task.
        taskID: The task ID associated with the audio file.

    returns:
        tuple: A tuple containing the async generator and the response object.
    
    raises:
        fastapi.HTTPException: If the file cannot be retrieved from storage.
    """
    
    path = getExportAudioPath(userID=userID, taskID=taskID, separated=False)
    
    LOGGER.info(f"[ASSETS] Getting export audio from storage at path: {path}")

    return await mental_storage_service.getFileFromStorageStream(
        path=path,
        mediaType="audio/mpeg"
    )



async def getExportTemplate(
    filename: str,
) -> tuple[typing.AsyncGenerator[bytes, None], httpx.Response]:
    """
    Get an export template file from storage as a stream.

    args:
        filename: The template file name.

    returns:
        tuple: A tuple containing the async generator and the response object.
    
    raises:
        fastapi.HTTPException: If the file cannot be retrieved from storage.
    """
    
    path = getExportTemplatePath(filename=filename, separated=False)
    
    LOGGER.info(f"[ASSETS] Getting export template from storage at path: {path}")

    return await mental_storage_service.getFileFromStorageStream(
        path=path,
        mediaType="audio/mpeg"
    )



async def getMakerStaticAudio(
    hashedText: str,
) -> tuple[typing.AsyncGenerator[bytes, None], httpx.Response]:
    """
    Get a maker static audio file from storage as a stream.

    args:
        hashedText: The hashed text (SHA256) used as filename.

    returns:
        tuple: A tuple containing the async generator and the response object.
    
    raises:
        fastapi.HTTPException: If the file cannot be retrieved from storage.
    """
    
    path = getMakerStaticAudioPath(hashedText=hashedText, separated=False)
    
    LOGGER.info(f"[ASSETS] Getting maker static audio from storage at path: {path}")

    return await mental_storage_service.getFileFromStorageStream(
        path=path,
        mediaType="audio/mpeg"
    )



async def getAssetFromPath(
    path: str,
    mediaType: str = "application/octet-stream"
) -> tuple[typing.AsyncGenerator[bytes, None], httpx.Response]:
    """
    Get an asset from storage using a custom path.

    args:
        path: The full path to the file in storage.
        mediaType: The media type of the file. Defaults to "application/octet-stream".

    returns:
        tuple: A tuple containing the async generator and the response object.
    
    raises:
        fastapi.HTTPException: If the file cannot be retrieved from storage.
    """
    
    LOGGER.info(f"[ASSETS] Getting asset from storage at path: {path}")

    return await mental_storage_service.getFileFromStorageStream(
        path=path,
        mediaType=mediaType
    )



# MARK: Delete Operations (agregar después de deleteExportTemplate)



async def deleteMakerStaticAudio(
    hashedText: str,
) -> None:
    """
    Delete a maker static audio file from storage.

    args:
        hashedText: The hashed text (SHA256) used as filename.
    
    raises:
        fastapi.HTTPException: If the file cannot be deleted from storage.
    """
    
    path = getMakerStaticAudioPath(hashedText=hashedText, separated=False)
    
    LOGGER.info(f"[ASSETS] Deleting maker static audio from storage at path: {path}")

    await mental_storage_service.deleteFileFromStorage(path=path)