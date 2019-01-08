#!/usr/bin/env python3
import click
import tendo.singleton
import time
import os.path
import subprocess
import re


def parse_xrandr_output(text):
    pattern = re.compile(r"^([\w-]+)\sconnected\s(primary)?\s?([0-9+x]+)?\s?.*")
    ret = filter(lambda x: pattern.match(x), text.decode("utf-8").splitlines())
    ret = map(lambda x: pattern.match(x).group(1), ret)
    ret = sorted(ret)

    # now, put the primary screen first, and rotate the ones before it to the
    # end
    for item in ret:
        if item[1] != "primary":
            ret.append(ret.pop(0))
        else:
            break
    return ret


def current_connected_displays():
    proc = subprocess.run(["xrandr"], stdout=subprocess.PIPE)
    output = proc.stdout
    ret = parse_xrandr_output(output)
    return ret


def script_name(displays):
    return os.path.expanduser(
        os.path.join("~", ".screenlayout", "_".join(displays) + ".sh")
    )


def run_script(path):
    try:
        subprocess.run([path])
        return True
    except Exception as e:
        print("Could not run script:", e)
        return False


def set_xrandr_with_script(path):
    if not run_script(path):
        subprocess.run(["xrandr", "-s", "0"])


def write_xresource(displays):

    xresourcefile = os.path.expanduser(os.path.join("~", ".Xresources.d", "i3"))
    data = """
! ~/.Xresources.d/i3

! Make sure to include this file from ~/.Xresources by adding
! #include "~/.Xresources.d/i3"

! output index 0 is the primary monitor, hence i3.output.0 == i3.output.primary
! output index 1 is the first secondary monitor, hence i3.output.1 == i3.output.secondary

"""

    index = 0
    for displayname in displays:
        data = data + "\ni3.output.{}: {}".format(index, displayname)
        if index == 0:
            data = data + "\ni3.output.primary: {}".format(displayname)
        elif index == 1:
            data = data + "\ni3.output.secondary: {}".format(displayname)
        data = data + "\n"
        index = index + 1
    data = data + "\n"

    f = open(xresourcefile, "w")
    f.write(data)
    f.close()

    # Reloading X server resource database utility
    subprocess.run(["xrdb", os.path.expanduser("-I$HOME"),os.path.expanduser("~/.Xresources")], stdout=subprocess.PIPE)
    subprocess.run(["i3-msg", "reload"], stdout=subprocess.PIPE)

def loop(post, once):

    if once:
        print("ONCE")
        new = current_connected_displays()
        handle_x(new, post)
    else:
        previous = ""
        while True:
            new = current_connected_displays()
            if new != previous:
                previous = new
                handle_x(new, post)
            time.sleep(1)

def handle_x(displays, post):

    script = script_name(displays)
    print("changed:", displays, ", calling:", script)
    set_xrandr_with_script(script)
    write_xresource(displays)
    if post:
        #print("calling post:", post)
        run_script(post)


@click.option("--post", default=None, help="program to run after a change")
@click.option("--once", is_flag=True, help="just run once and update")
@click.command()
def main(post, once):
    if not once:
        instance = tendo.singleton.SingleInstance()
    loop(post, once)


if __name__ == "__main__":
    main()
