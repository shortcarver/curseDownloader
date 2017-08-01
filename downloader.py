#!python3
from urllib.parse import urlparse, unquote

import sys
import appdirs
import argparse
import json
from pathlib import Path
import os
import requests
import shutil
from threading import Thread
from tkinter import *
from tkinter import ttk, filedialog

parser = argparse.ArgumentParser(description="Download Curse modpack mods")
parser.add_argument("--manifest", help="manifest.json file from unzipped pack")
args, unknown = parser.parse_known_args()

class headlessUI():
    def setOutput(self, message):
        pass

programGui = None

def doDownload(manifest):
    manifestPath = Path(manifest)
    targetDirPath = manifestPath.parent

    manifestText = manifestPath.open().read()
    manifestText = manifestText.replace('\r', '').replace('\n', '')

    manifestJson = json.loads(manifestText)

    overridePath = Path(targetDirPath, manifestJson['overrides'])
    minecraftPath = Path(targetDirPath, "minecraft")
    if overridePath.exists():
        shutil.move(str(overridePath), str(minecraftPath))

    downloaderDirs = appdirs.AppDirs(appname="cursePackDownloader", appauthor="portablejim")
    cache_path = Path(downloaderDirs.user_cache_dir, "curseCache")

    # Attempt to set proper portable data directory if asked for
    if '__file__' in globals():
        cache_path = Path(os.path.dirname(os.path.realpath(__file__)), "CPD_data")
    else:
        print("Portable data dir not supported for interpreter environment")
        exit(2)

    if not cache_path.exists():
        cache_path.mkdir(parents=True)
    print("Cache path : %s" % (cache_path))

    if not minecraftPath.exists():
        minecraftPath.mkdir()

    modsPath = minecraftPath / "mods"
    if not modsPath.exists():
        modsPath.mkdir()

    sess = requests.session()

    i = 1
    iLen = len(manifestJson['files'])

    print("%d files to download" % (iLen))
    programGui.setOutput("%d files to download" % (iLen))

    for dependency in manifestJson['files']:
        depCacheDir = cache_path / str(dependency['projectID']) / str(dependency['fileID'])
        if depCacheDir.is_dir():
            # File is cached
            depFiles = [f for f in depCacheDir.iterdir()]
            if len(depFiles) >= 1:
                depFile = depFiles[0]
                targetFile = minecraftPath / "mods" / depFile.name
                shutil.copyfile(str(depFile), str(targetFile))
                programGui.setOutput("[%d/%d] %s (cached)" % (i, iLen, targetFile.name))

                i += 1

                # Cache access is successful,
                # Don't download the file
                continue

        # File is not cached and needs to be downloaded
        projectResponse = sess.get("https://minecraft.curseforge.com/projects/%s" % (dependency['projectID']), stream=True, allow_redirects=False)
        
        auth_cookie = None
        for redirect in sess.resolve_redirects(projectResponse, projectResponse.request):
             sess.cookies.update({'Auth.Token': auth_cookie})
             if redirect.headers.get('Set-Cookie') is not None:
                  cookie_list = redirect.headers.get('Set-Cookie').split(";")[0].split("=")
                  if cookie_list[0] == 'Auth.Token':
                        auth_cookie = cookie_list[1]
             projectResponse.url = redirect.url

        fileResponse = sess.get("%s/files/%s/download" % (projectResponse.url, dependency['fileID']), stream=True)
        while fileResponse.is_redirect:
            source = fileResponse
            fileResponse = sess.get(source, stream=True)
        filePath = Path(fileResponse.url)
        fileName = unquote(filePath.name)
        print("[%d/%d] %s" % (i, iLen, fileName))
        programGui.setOutput("[%d/%d] %s" % (i, iLen, fileName))
        with open(str(minecraftPath / "mods" / fileName), "wb") as mod:
            mod.write(fileResponse.content)

        # Try to add file to cache.
        if not depCacheDir.exists():
            depCacheDir.mkdir(parents=True)
            with open(str(depCacheDir / fileName), "wb") as mod:
                mod.write(fileResponse.content)

        i += 1

    # This is not available in curse-only packs
    if 'directDownload' in manifestJson:
        i = 1
        i_len = len(manifestJson['directDownload'])
        programGui.setOutput("%d additional files to download." % i_len)
        for download_entry in manifestJson['directDownload']:
            if "url" not in download_entry or "filename" not in download_entry:
                programGui.setOutput("[%d/%d] <Error>" % (i, i_len))
                i += 1
                continue
            source_url = urlparse(download_entry['url'])
            download_cache_children = Path(source_url.path).parent.relative_to('/')
            download_cache_dir = cache_path / "directdownloads" / download_cache_children
            cache_target = Path(download_cache_dir / download_entry['filename'])
            if cache_target.exists():
                # Cached
                target_file = minecraftPath / "mods" / cache_target.name
                shutil.copyfile(str(cache_target), str(target_file))

                i += 1

                # Cache access is successful,
                # Don't download the file
                continue
            # File is not cached and needs to be downloaded
            file_response = sess.get(source_url, stream=True)
            while file_response.is_redirect:
                source = file_response
                file_response = sess.get(source, stream=True)
            programGui.setOutput("[%d/%d] %s" % (i, i_len, download_entry['filename']))
            with open(str(minecraftPath / "mods" / download_entry['filename']), "wb") as mod:
                mod.write(file_response.content)

            i += 1

programGui = headlessUI()
doDownload(args.manifest)


