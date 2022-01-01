import hashlib
import base64
import logging
from helper_func.fileFolderFuncs import cleanFolder, deleteFile
from helper_func.generateNewFilename import GenerateNewFilename
from helper_func.messageFuncs import editMessage, sendMessage
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('log.txt'), logging.StreamHandler()],
    level=logging.INFO)
LOGGER = logging.getLogger(__name__)
import os
import time
from config import Config
from pyrogram import Client, filters
from helper_func.progress import ProgressForPyrogram, TimeFormatter
from helper_func.auth_user_check import AuthUserCheck
from helper_func.progress import HumanBytes
from helper_func.force_sub import ForceSub

@Client.on_message(filters.command(Config.HASH_COMMAND))
async def FileHashBot(client, message):
    # user details
    chatId = message.chat.id
    userId = message.from_user.id
    # authorized user check
    if not await AuthUserCheck(chatId, userId):
        await sendMessage(message, Config.UNAUTHORIZED_TEXT_STR)
        return
    # force subscribe check
    if await ForceSub(client, message) == 400: return
    # replied message is none check
    if message.reply_to_message is None:
        await sendMessage(message, Config.START_TEXT_STR)
        return
    # is media
    if not message.reply_to_message.media:
        await sendMessage(message, Config.START_TEXT_STR)
        return
    # protect filesize and filename
    if message.reply_to_message.document:
        try:
            documentFilename = message.reply_to_message.document.file_name
        except:
            documentFilename = "File"
        try:
            documentFilesize = message.reply_to_message.document.file_size
        except:
            documentFilesize = 0
    elif message.reply_to_message.video:
        try:
            documentFilename = message.reply_to_message.video.file_name
        except:
            documentFilename = "File"
        try:
            documentFilesize = message.reply_to_message.video.file_size
        except:
            documentFilesize = 0
    elif message.reply_to_message.audio:
        try:
            documentFilename = message.reply_to_message.audio.file_name
        except:
            documentFilename = "File"
        try:
            documentFilesize = message.reply_to_message.audio.file_size
        except:
            documentFilesize = 0
    #else:
        #await sendMessage(message, Config.UNSUPPORTED_FILE_TYPE_STR)
        #return
    if documentFilesize == None: documentFilesize = 0
    if documentFilename == None: documentFilename = "File"
    # download folder and file for each user
    downloadFolder = os.path.join(Config.DOWNLOAD_DIR, str(userId))
    downloadedFile = await GenerateNewFilename(os.path.join(downloadFolder, documentFilename))
    # clear if user folder is empty
    try:
        if len(os.listdir(downloadFolder)) == 0: os.rmdir(downloadFolder)
    except Exception as e: LOGGER.info(str(e))
    # one process per user
    if Config.ONE_PROCESS_PER_USER:
        if os.path.isdir(downloadFolder):
            await sendMessage(message, Config.ONE_PROCESS_PER_USER_STR)
            return
    if not os.path.isdir(downloadFolder):
        try:
            os.mkdir(downloadFolder)
            LOGGER.info("download folder created for: " + downloadFolder)
        except Exception as e:
            await sendMessage(message, str(e))
            return
    # check filesize limit before download
    if Config.DOWNLOAD_LIMIT != 0:
        if Config.DOWNLOAD_LIMIT < documentFilesize:
            await sendMessage(message,
                f"🇬🇧 Size limit: {Config.DOWNLOAD_LIMIT} Your file: {str(documentFilesize)}\n" + \
                f"🇬🇧 Boyut sınırı: {Config.DOWNLOAD_LIMIT} Senin dosyan: {str(documentFilesize)}"
            )
            return
    # download file
    downloadStartTime = time.time()
    downloadingMessage = await sendMessage(message, "🇬🇧 I am looking / 🇹🇷 Bekle bakim az")
    if documentFilesize > Config.SHOW_PROGRESS_MIN_SIZE_DOWNLOAD:
        try:
            LOGGER.info("document size was bigger than config. showing process.")
            downloadedFileLocation = await client.download_media(
                message=message.reply_to_message,
                file_name=downloadedFile,
                progress=ProgressForPyrogram,
                progress_args=(
                    Config.DOWNLOADING_STR.format(str(documentFilename),
                    HumanBytes(documentFilesize)
                    ),
                downloadingMessage,
                downloadStartTime
                )
            )
        except Exception as e:
            await downloadingMessage.edit(
                text=f"🇹🇷 İndirme Başarısız / 🇬🇧 Download Failed.\n\n{str(e)}",
                parse_mode='markdown')
            if Config.ONE_PROCESS_PER_USER: await cleanFolder(downloadFolder)
            return
    else:
        LOGGER.info("Ignoring file size: " + str(documentFilesize))
        try:
            LOGGER.info("document size was smaller than config. no need to showing process.")
            downloadedFileLocation = await client.download_media(
                message=message.reply_to_message,
                file_name=downloadedFile,
            )
        except Exception as e:
            await downloadingMessage.edit(
                text=f"🇹🇷 İndirme Başarısız / 🇬🇧 Download Failed.\n\n{str(e)}",
                parse_mode='markdown')
            if Config.ONE_PROCESS_PER_USER: await cleanFolder(downloadFolder)
            return
    downloadFinishTime = time.time()
    # check file downloaded
    if downloadedFile == None or downloadedFileLocation == None:
        await downloadingMessage.edit(text=f"🇹🇷 İndirme Başarısız / 🇬🇧 Download Failed.", parse_mode='markdown')
        if Config.ONE_PROCESS_PER_USER: await cleanFolder(downloadFolder)
        return
    # downloaded message
    downloadCompleteText = Config.DOWNLOAD_SUCCESS.format(TimeFormatter((downloadFinishTime - downloadStartTime) * 1000))
    await editMessage(downloadingMessage, downloadCompleteText)
    LOGGER.info("downloadedFile: " + str(downloadedFile))
    LOGGER.info("downloadedFileLocation: " + str(downloadedFileLocation))
    # hashing
    hashStartTime = time.time()
    try:
        with open(downloadedFileLocation, "rb") as f:
            md5 = hashlib.md5()
            while chunk := f.read(8192):
                md5.update(chunk)
    except Exception as a:
        LOGGER.info(str(a))
        await downloadingMessage.edit(text=f"Hashing error.\n\n{str(a)}",
            parse_mode='markdown')
        await deleteFile(documentFilename)
        await deleteFile(downloadedFileLocation)
        if Config.ONE_PROCESS_PER_USER: await cleanFolder(downloadFolder)
        return
    # hash text
    hashFinishTime = time.time()
    finishedText = "File: `{}`\n".format(documentFilename)
    finishedText += "Size: `{}`\n".format(HumanBytes(documentFilesize))
    finishedText += "MD5: `{}`\n".format(md5.hexdigest())
    timeTaken = f"🥚 Hash Time / İşlem Süresi: `{TimeFormatter((hashFinishTime - hashStartTime) * 1000)}`"
    await editMessage(downloadingMessage, Config.HASH_SUCCESS.format(finishedText))
    # clean folder if one process per user
    await deleteFile(downloadedFile)
    await deleteFile(downloadedFileLocation)
    if Config.ONE_PROCESS_PER_USER: await cleanFolder(downloadFolder)
