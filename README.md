# refern-takeout

Unofficial tool for downloading a dump of all of your images, collections, boards and folders from refern.


## Caveats

* While I'll try to make this documentation as accessible as I can, you still need to have a little bit of experience with using browser devtools and running Python scripts to be able to use this.
* This tool requires login details. While it should be possible to download public boards without needing to provide login details, I haven't implemented it.
* This tool saves your refern data in pretty much the raw form provided by the internal API.
  Images are saved as-is, but boards and image metadata are saved as JSON files.
  Turning these JSON files into anything human-readable e.g. a visual render of the board as displayed in refern is left as an exercise to the reader (or another keen coder).
  I've only implemented the bare minimum needed to get your data out of the app before the servers get switched off.


## Installation

1. Install [Python][], if you haven't already.

   For Windows: https://www.python.org/ftp/python/3.13.7/python-3.13.7-amd64.exe

   For macOS: https://www.python.org/ftp/python/3.13.7/python-3.13.7-macos11.pkg

   For Linux: it's almost certainly pre-installed

2. [Download refern-takeout][] and extract the ZIP file on your computer.


## Using refern-takeout

1. Find your refern account username, beginning with `@`. This is usually displayed at the top right corner of the screen when logged into the app (on desktop).

2. Find your refern authorization token. Detailed steps below.

   **Treat your auth token the same way you'd treat your password. Anyone who possesses it has full access over your account.**

   a. Open [refern][refern-app] in your web browser, ensuring you're logged in.

   b. Open your browser's developer tools. On Google Chrome this can be found in the menu here:

      ![More tools -> Developer tools](doc/images/devtools-chrome-menu.png)

   c. Select the Network tab, and copy/paste `prod.api.refern.app method:GET` into the filter box.

      ![](doc/images/devtools-chrome-filter.png)

   d. Select any one of the items in the list below, and make sure the Headers tab is selected in the pane that appears.
      Your authorization token is the long string of text, likely beginning with "ey", appearing to the right of the word "Authorization".

      ![](doc/images/devtools-chrome-request-2.png)

   **Treat your auth token the same way you'd treat your password. Anyone who possesses it has full access over your account.**

3. In a shell/command line, run:

       python3 refern_takeout.py -u @yourusername

   where `@yourusername` is your username from step 1. When prompted for your authorization token, copy-paste it from where you found it in the developer tools in step 2.

4. Your refern content will be downloaded into a new folder named `refern`, located in the same folder as the `refern_takeout.py` script.


[Download refern-takeout]: https://github.com/kierdavis/refern-takeout/archive/refs/heads/main.zip
[Python]: https://www.python.org/
[refern-app]: https://my.refern.app/
