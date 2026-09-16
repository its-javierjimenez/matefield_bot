import tenacity
import logging
import httpx
import anyio
import typing
import fastapi
from hypnosis_utils.logger import getLogger
from src.modules.v1.shared.connections.apis import mental_storage as mental_storage_connections

LOGGER = getLogger("v1.shared.services.mental_storage")

@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=1, max=30),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError, fastapi.HTTPException)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def submitFileToStorage(
    file : typing.BinaryIO,
    fileName: str,
    folderName: str,
    contentType: str,
    privacy : str = "private",
) -> None:
    """
    Submits a file to the mental storage service.

    args:
        file: The file content to upload.
        fileName: The name of the file.
        folderName: The folder to upload the file to.
        privacy: The privacy level of the file. Defaults to "private".
        contentType: The content type of the file.

    raises:
        fastapi.HTTPException: If the file cannot be uploaded to storage.
    """

    LOGGER.info(f"[MENTAL][STORAGE] Subiendo archivo '{fileName}' a storage")

    response = await mental_storage_connections.MENTAL_STORAGE_CLIENT.post(
        "/createFile",
        
        headers= httpx.Headers({
            "filename" : fileName,
            "folder" : folderName,
            "privacy" : privacy,
            "content-type" : contentType,
        }),

        files={
            "file": file
        },

        timeout= httpx.Timeout(None)
    )
    
    if not response.is_success:
        LOGGER.info(f"[MENTAL][STORAGE] Error uploading file {fileName} to storage: {response.status_code} - {response.text}")
        raise fastapi.HTTPException(
            status_code=response.status_code,
            detail=f"Error uploading file {fileName} to storage: {response.status_code} - {response.text}"
        )
    
    LOGGER.info(f"[MENTAL][STORAGE] Archivo {fileName} subido exitosamente a storage")



@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=1, max=30),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError, fastapi.HTTPException)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def submitFileToStorageAsStream(
    asyncGenerator: typing.AsyncGenerator[bytes],
    fileName: str,
    folderName: str,
    contentType: str,
    privacy: str = "private",
) -> None:
    """
    Submits a file to the mental storage service.

    args:
        file: The file content to upload.
        fileName: The name of the file.
        folderName: The folder to upload the file to.
        privacy: The privacy level of the file. Defaults to "private".
        contentType: The content type of the file.

    raises:
        fastapi.HTTPException: If the file cannot be uploaded to storage.
    """
    LOGGER.info(f"[MENTAL][STORAGE] Subiendo archivo '{fileName}' a storage")

    response = await mental_storage_connections.MENTAL_STORAGE_CLIENT.post(
        "/createFile",
        
        headers= httpx.Headers({
            "filename" : fileName,
            "folder" : folderName,
            "privacy" : privacy,
            "content-type" : contentType,
        }),

        content=asyncGenerator,

        timeout= httpx.Timeout(None)
    )
    
    if not response.is_success:
        LOGGER.info(f"[MENTAL][STORAGE] Error uploading file {fileName} to storage: {response.status_code} - {response.text}")
        raise fastapi.HTTPException(
            status_code=response.status_code,
            detail=f"Error uploading file {fileName} to storage: {response.status_code} - {response.text}"
        )
    
    LOGGER.info(f"[MENTAL][STORAGE] Archivo {fileName} subido exitosamente a storage")


@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=1, max=30),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def checkIfFileInStorage(
    path: str,
    checkSize: bool = True,
) -> bool:
    """
    Checks if a file exists in storage and optionally validates it's not empty.

    args:
        path: The path to the file in storage.
        checkSize: If True, also validates that the file is not empty (size > 0). Defaults to True.

    returns:
        bool: True if the file exists (and is not empty if checkSize=True), False otherwise.

    raises:
        fastapi.HTTPException: If the file exists but is empty (0 bytes) when checkSize=True.
    """
    
    LOGGER.info(f"[MENTAL][STORAGE] Chequeando archivo '{path}' en storage (checkSize={checkSize})")

    # First, check if file exists with HEAD
    response = await mental_storage_connections.MENTAL_STORAGE_CLIENT.head(
        "/getFile",
        headers=httpx.Headers({
            "path": path,
        }),
        timeout=httpx.Timeout(None)
    )
    
    if not response.is_success:
        LOGGER.warning(f"[MENTAL][STORAGE] File {path} not found in storage: {response.status_code}")
        return False
    
    # If checkSize is False, we're done
    if not checkSize:
        LOGGER.info(f"[MENTAL][STORAGE] File {path} exists")
        return True
    
    # Get just the first byte to check if file is empty
    # Using Range header to minimize data transfer
    LOGGER.info(f"[MENTAL][STORAGE] Validating file size for '{path}'")
    
    sizeCheckResponse = await mental_storage_connections.MENTAL_STORAGE_CLIENT.get(
        "/getFile",
        headers=httpx.Headers({
            "path": path,
            "Range": "bytes=0-0",  # Request only first byte
        }),
        timeout=httpx.Timeout(None)
    )

    if not sizeCheckResponse.is_success:
        LOGGER.error(f"[MENTAL][STORAGE] Error checking size of file {path} in storage: {sizeCheckResponse.status_code} - {sizeCheckResponse.text}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking size of file {path} in storage: {sizeCheckResponse.status_code} - {sizeCheckResponse.text}"
        )
    
    # Read the response to check if we got any content
    content = await sizeCheckResponse.aread()
    fileSize = len(content)
    
    # Close the response
    await sizeCheckResponse.aclose()
    
    if fileSize == 0:
        LOGGER.error(f"[MENTAL][STORAGE] File {path} exists but is empty (0 bytes)")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"File {path} exists but is empty (0 bytes). Upload may have failed."
        )
    
    # Check if we got Content-Range or Content-Length from the partial response
    contentRange = sizeCheckResponse.headers.get("content-range")
    contentLength = sizeCheckResponse.headers.get("content-length")
    
    if contentRange:
        # Format: "bytes 0-0/12345" -> extract total size
        try:
            totalSize = int(contentRange.split('/')[-1])
            LOGGER.info(f"[MENTAL][STORAGE] File {path} exists and is valid (size: {totalSize} bytes)")
        except (ValueError, IndexError):
            LOGGER.info(f"[MENTAL][STORAGE] File {path} exists and is not empty (size: >0 bytes)")
    elif contentLength:
        LOGGER.info(f"[MENTAL][STORAGE] File {path} exists and is valid (size: {contentLength} bytes)")
    else:
        LOGGER.info(f"[MENTAL][STORAGE] File {path} exists and is not empty (size: >0 bytes)")
    
    return True

@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=1, max=30),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def getFileFromStorage(
    path: str,
    mediaType: str
) -> typing.AsyncIterator[bytes]:
    """
    Gets a file from storage by loading it into memory.
    """
    
    LOGGER.info(f"[MENTAL][STORAGE] Obteniendo archivo '{path}' de storage")

    response = await mental_storage_connections.MENTAL_STORAGE_CLIENT.get(
        "/getFile",
        headers=httpx.Headers({
            "path": path,
            "content-type": mediaType
        }),
        
        timeout=httpx.Timeout(None)
    )
    
    if not response.is_success:
        LOGGER.info(f"[MENTAL][STORAGE] Error getting file {path} from storage: {response.status_code} - {response.text}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"Error getting file {path} from storage: {response.status_code} - {response.text}"
        )
    
    LOGGER.info(f"[MENTAL][STORAGE] Archivo {path} obtenido exitosamente de storage")

    return response.aiter_bytes()

@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=1, max=30),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def getFileFromStorageStream(
    path: str,
    mediaType : str,
) -> typing.Tuple[typing.AsyncGenerator[bytes, None], httpx.Response]:
    
    LOGGER.info(f"[MENTAL][STORAGE] Obteniendo archivo '{path}' de storage")

    request = mental_storage_connections.MENTAL_STORAGE_CLIENT.build_request(
        method="GET",
        url="/getFile",
        headers=httpx.Headers({
            "path": path,
            "content-type": mediaType
        }),
        timeout=httpx.Timeout(None),
    )
    
    response = await mental_storage_connections.MENTAL_STORAGE_CLIENT.send(request, stream=True)

    if not response.is_success:
        await response.aread()  # Leer el contenido para liberar la conexión
        LOGGER.info(f"[MENTAL][STORAGE] Error getting file {path} from storage: {response.status_code} - {response.text}")
        await response.aclose()  # Cerrar la respuesta para liberar la conexión
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"Error getting file {path} from storage: {response.status_code} - {response.text}"
        )

    return response.aiter_bytes(), response

@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=1, max=30),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError, fastapi.HTTPException)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def deleteFileFromStorage(
    path: str,
) -> None:
    
    LOGGER.info(f"[MENTAL][STORAGE] Eliminando archivo '{path}' de storage")

    response = await mental_storage_connections.MENTAL_STORAGE_CLIENT.delete(
        "/deleteFile",
        headers=httpx.Headers({
            "path": path,
        }),
        timeout=httpx.Timeout(None)
    )
    
    if not response.is_success:
        LOGGER.info(f"[MENTAL][STORAGE] Error deleting file {path} from storage: {response.status_code} - {response.text}")
        raise fastapi.HTTPException(
            status_code=response.status_code,
            detail=f"Error deleting file {path} from storage: {response.status_code} - {response.text}"
        )
    
    LOGGER.info(f"[MENTAL][STORAGE] Archivo {path} eliminado exitosamente de storage")



@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=1, max=30),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError, fastapi.HTTPException)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def updateFileInStorage(
    file: bytes,
    fileName: str,
    folderName: str,
    contentType: str,
    privacy: str = "private"
) -> None:
    """
    Update a file in storage.

    args:
        file: The file content to update.
        fileName: The name of the file.
        folderName: The name of the folder.
        contentType: The content type of the file.
        privacy: The privacy setting of the file. Default is "private".
    """
    
    LOGGER.info(f"[MENTAL][STORAGE] Actualizando archivo '{fileName}' en storage")

    response = await mental_storage_connections.MENTAL_STORAGE_CLIENT.put(
        "/updateFile",
        
        headers=httpx.Headers({
            "fileName": fileName,
            "folder": folderName,
            "privacy": privacy,
            "content-type": contentType,
        }),
        
        content=file,
        
        timeout=httpx.Timeout(None)
    )
    
    if not response.is_success:
        LOGGER.info(f"[MENTAL][STORAGE] Error updating file {fileName} in storage: {response.status_code} - {response.text}")
        raise fastapi.HTTPException(
            status_code=response.status_code,
            detail=f"Error updating file {fileName} in storage: {response.status_code} - {response.text}"
        )
    
    LOGGER.info(f"[MENTAL][STORAGE] Archivo {fileName} actualizado exitosamente en storage")

@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=1, max=30),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError, fastapi.HTTPException)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def updateFileInStorageAsStream(
    asyncGenerator: typing.AsyncGenerator[bytes],
    fileName: str,
    folderName: str,
    contentType: str,
    privacy: str = "private"
) -> None:
    """
    Update a file in storage using a stream.

    args:
        asyncGenerator: Async generator that yields file content bytes.
        fileName: The name of the file.
        folderName: The name of the folder.
        contentType: The content type of the file.
        privacy: The privacy setting of the file. Default is "private".

    raises:
        fastapi.HTTPException: If the file cannot be updated in storage.
    """
    
    LOGGER.info(f"[MENTAL][STORAGE] Actualizando archivo '{fileName}' en storage (stream)")

    response = await mental_storage_connections.MENTAL_STORAGE_CLIENT.put(
        "/updateFile",
        
        headers=httpx.Headers({
            "fileName": fileName,
            "folder": folderName,
            "privacy": privacy,
            "content-type": contentType,
        }),
        
        content=asyncGenerator,
        
        timeout=httpx.Timeout(None)
    )
    
    if not response.is_success:
        LOGGER.info(f"[MENTAL][STORAGE] Error updating file {fileName} in storage: {response.status_code} - {response.text}")
        raise fastapi.HTTPException(
            status_code=response.status_code,
            detail=f"Error updating file {fileName} in storage: {response.status_code} - {response.text}"
        )
    
    LOGGER.info(f"[MENTAL][STORAGE] Archivo {fileName} actualizado exitosamente en storage (stream)")

if __name__ == "__main__":
    import asyncio
    import dotenv

    dotenv.load_dotenv(
        override=True,
    )

    async def main():
        # Example usage
        await checkIfFileInStorage("final_audios/676f502de85626092f616863/68c4d37416315b0dc2db1fe0/audio.mp3")
    
    asyncio.run(main())