#!/usr/bin/env python3

import argparse
import datetime
import json
import getpass
import pathlib
import shutil
import sys
import time
import urllib.request
from pprint import pformat
from urllib.error import HTTPError


MAX_EXPORT_AGE = datetime.timedelta(hours=12)


def main():
  args = parse_args()
  if args.debug:
    globals()["debug_log"] = log
  else:
    globals()["debug_log"] = lambda _: None

  if args.output:
    output_dir = pathlib.Path(args.output)
  else:
    output_dir = pathlib.Path.cwd() / "refern"

  api = API(load_api_token(args.token_file))

  user_id = api.get_user_id_by_username(args.username)
  debug_log(f"user_id = {user_id!r}")

  folders = {x["_id"]: x for x in api.get_folders(user_id)}
  debug_log(f"folders = {pformat(folders)}")

  items = [{**item, "__parentFolderId": folder_id} for folder_id in folders for item in api.get_folder_items(folder_id)]
  compute_fullnames(folders, items)
  debug_log(f"items = {pformat(items)}")

  dump_boards((item for item in items if item["type"] == "board"), api, output_dir)
  dump_collections([item for item in items if item["type"] == "collection"], api, user_id, output_dir)


def parse_args():
  p = argparse.ArgumentParser()
  p.add_argument("-u", "--username", required=True, metavar="USERNAME", help="The username/handle of your refern account (the one beginning with '@').")
  p.add_argument("-t", "--token-file", metavar="PATH", help="Path to a file containing your authorization token. If omitted, you'll be prompted for the token interactively.")
  p.add_argument("-o", "--output", metavar="DIR", help="Path to a directory to save images/collections/boards to. If omitted, defaults to a new directory named 'refern' in the current working directory.")
  p.add_argument("-d", "--debug", action="store_true", help="Show debug messages.")
  return p.parse_args()


def load_api_token(path):
  if path:
    with open(path, "r") as f:
      return f.read().strip()
  else:
    return getpass.getpass("Authorization token (see README.md for how to find this): ").strip()


def compute_fullnames(folders, items):
  for folder_id, folder in folders.items():
    folder["__fullname"] = compute_folder_fullname(folder_id, folders)
  for item in items:
    item["__fullname"] = folders[item["__parentFolderId"]]["__fullname"] + "/" + item["name"].replace("/", "_")


def compute_folder_fullname(folder_id, folders):
  base_name = folders[folder_id]["name"].replace("/", "_")
  parent_id = folders[folder_id]["parentFolderId"]
  if parent_id:
    return compute_folder_fullname(parent_id, folders) + "/" + base_name
  else:
    return base_name


def dump_boards(boards, api, output_dir):
  for board in boards:
    log(f"board {board['_id']} \"{board['__fullname']}\": downloading...")
    board_data = api.get_board(board["_id"])
    dest_path = output_dir / (board["__fullname"] + ".json")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w") as f:
      json.dump(board_data, f, separators=(',', ':'))


def dump_collections(collections, api, user_id, output_dir):
  ex = CollectionExporter(collections=collections, api=api, user_id=user_id)
  ex.trigger_if_outdated(max_age=MAX_EXPORT_AGE)
  ex.wait_until_all_completed()
  log("all collections ready for download")
  for c in collections:
    log(f"collection {c['_id']} \"{c['__fullname']}\": downloading...")
    download(ex.url_for(c["_id"]), output_dir / (c["__fullname"] + ".zip"))


def download(url, dest_path):
  dest_path.parent.mkdir(parents=True, exist_ok=True)
  with open(dest_path, "wb") as f:
    with urllib.request.urlopen(url) as resp:
      shutil.copyfileobj(resp, f)


class CollectionExporter:
  def __init__(self, collections, api, user_id):
    self.collections = collections
    self.api = api
    self.user_id = user_id
    self.statuses = {c["_id"]: api.get_collection_export_status(c["_id"]) for c in collections}

  def trigger_if_outdated(self, max_age):
    for c in self.collections:
      s = self.statuses[c["_id"]]
      if s is None:
        log(f"collection {c['_id']} \"{c['__fullname']}\": has never been exported; initiating export")
        self.trigger_export(c["_id"])
      else:
        last_export = datetime.datetime.fromtimestamp(max(s["exportTimes"]) / 1000, datetime.timezone.utc)
        age = datetime.datetime.now(tz=datetime.timezone.utc) - last_export
        if age > max_age:
          log(f"collection {c['_id']} \"{c['__fullname']}\": last export was at {last_export}; initiating new export")
          self.api.delete_collection_export(c["_id"], s["_id"])
          self.trigger_export(c["_id"])
        else:
          log(f"collection {c['_id']} \"{c['__fullname']}\": using recent export from {last_export}")

  def trigger_export(self, collection_id):
    self.statuses[collection_id] = self.api.trigger_collection_export(collection_id, self.user_id)

  def wait_until_all_completed(self):
    while True:
      pending_cids = [cid for cid, s in self.statuses.items() if s["status"] != "completed"]
      if pending_cids:
        log("waiting for:")
        for cid in pending_cids:
          log(f"  {cid}: status={self.statuses[cid]['status']}")
        time.sleep(10)
        for cid in pending_cids:
          self.statuses[cid] = self.api.get_collection_export_status(cid)
      else:
        break

  def url_for(self, collection_id):
    return self.statuses[collection_id]["downloadUrl"]


class API:
  def __init__(self, token):
    self.token = token

  def get_user_id_by_username(self, username):
    username = username.lstrip("@")
    return self._call(f"/user/at/{username}", response_fmt="json")["_id"]

  def get_folders(self, user_id):
    return self._call(f"/folder/user/{user_id}", response_fmt="json")

  def get_folder_items(self, folder_id):
    return self._call(f"/folder/{folder_id}/item", response_fmt="json")

  def get_board(self, board_id):
    return self._call(f"/board/{board_id}", response_fmt="json")

  def get_collection_export_status(self, collection_id):
    try:
      return self._validate_collection_export_status(
        self._call(f"/collection/download/{collection_id}", response_fmt="json"),
      )
    except HTTPError as e:
      if e.code == 404:
        return None
      else:
        raise

  def trigger_collection_export(self, collection_id, user_id):
    return self._validate_collection_export_status(
      self._call(
        f"/collection/download/{collection_id}",
        json_data={
          "collectionMetadataExportFileType": "json",
          "creatorUserId": user_id,
          "imageMetadataExportFileType": "json",
        },
        response_fmt="json",
      ),
    )

  def delete_collection_export(self, collection_id, export_id):
    self._call(
      f"/collection/download/{export_id}",
      method="DELETE",
      headers={
        "Resource-Id": collection_id,
        "Resource-Type": "collection",
      },
    )

  def _validate_collection_export_status(self, resp_data):
    if resp_data["status"] not in {"started", "completed", "deleted"}:
      raise NotImplementedError(resp_data["status"])
    return resp_data

  def _call(self, url_path, method=None, headers={}, json_data=None, response_fmt=None):
    req = urllib.request.Request(
      url = "https://prod.api.refern.app" + url_path,
      method = method,
      headers = {
        **headers,
        "Authorization": self.token,
        "Origin": "https://my.refern.app",
        "Referer": "https://my.refern.app",
      },
    )
    if json_data is not None:
      req.data = json.dumps(json_data, separators=(',', ':')).encode("utf-8")
      req.add_header("Content-Type", "application/json")
    if response_fmt == "json":
      req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req) as resp:
      assert resp.status < 300 # urlopen should have raised HTTPError
      if response_fmt is None:
        return None
      elif response_fmt == "json":
        assert "application/json" in resp.getheader("Content-Type")
        return json.load(resp)
      else:
        raise ValueError(response_fmt)


def log(msg):
  print(msg, file=sys.stderr)


if __name__ == "__main__":
  main()
