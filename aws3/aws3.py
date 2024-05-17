import logging
import os
import random

import click
import yaml

from . import utils as u
from .utils import cf, ec2

try:
    from defaultlog import log
except:
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger()

for logger in ["botocore", "numexpr"]:
    logging.getLogger(logger).setLevel(logging.WARNING)

HERE = os.path.dirname(os.path.abspath(__file__))


class OrderCommands(click.Group):
    """make help message show commands in order defined not alphabetical"""

    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands)


@click.group(cls=OrderCommands)
def c():
    """cli to start/stop instances"""
    pass


@c.command(help="start a stack from a template args=template [name]")
@click.argument("template")
@click.argument("name", default="", required=False)
def start(template, name=""):
    """start stack from templates/{name}.yaml"""
    params = dict()

    # get template
    base, ext = os.path.splitext(template)
    if not ext and not os.path.isfile(template):
        template = f"{HERE}/templates/{base}.yaml"
    stack = yaml.safe_load(open(template).read())

    if name:
        images = u.get_images(**u.tag(Name=name))
        if images:
            # existing image
            params["ImageId"] = images[-1].id
    else:
        # generate name for new image
        with open(f"{HERE}/names.csv") as f:
            names = f.read().split("\n")
        # avoid existing images
        image_names = [u.get_tags(x).get("Name", "unknown") for x in u.get_images()]
        names = list(set(names) - set(image_names))
        name = random.choice(names)

    # launch
    params["Name"] = name
    log.info(f"launching {name} with template {base}")
    res = cf.create_stack(
        StackName=name,
        TemplateBody=yaml.dump(stack),
        Parameters=u.params(**params),
    )


@c.command(help="create image and stop stack args=name")
@click.argument("name")
def stop(name):
    """create image and stop stack"""
    save = True
    # get instance
    try:
        InstanceId = u.get_instances(**u.tag(Name=name))[0]["InstanceId"]
    except IndexError:
        log.warning("instance not found so could not be stopped")
        save = False

    if save:
        # create image
        log.info(f"saving image {name}")
        r = ec2.create_image(
            InstanceId=InstanceId,
            # Name=> AMI_Name; Name=>Name; name shortcut for search
            Name=name + " " + InstanceId,
            TagSpecifications=[
                dict(ResourceType="image", Tags=u.tags(Name=name, name=name)),
                dict(ResourceType="snapshot", Tags=u.tags(Name=name, name=name)),
            ],
        )
        # wait until snapshot complete before removing images and stack
        ec2.get_waiter("image_available").wait(ImageIds=[r["ImageId"]])

        # remove old images
        log.info(f"removing old images {name}")
        images = u.get_images(**u.tag(Name=name))
        for image in images[:-1]:
            ec2.deregister_image(ImageId=image.id)

    # remove stack
    log.info(f"removing stack {name}")
    cf.delete_stack(StackName=name)
    cf.get_waiter("stack_delete_complete").wait(StackName=name)

    log.info("stop completed")
    show.callback()


@c.command(help="terminate stack. does not delete AMI/snapshots. args=name")
@click.argument("name")
def terminate(name):
    """delete stack with name"""
    stacks = [x["StackName"] for x in u.get_stacks()]
    if name in stacks:
        log.info(f"terminating {name}")
        cf.delete_stack(StackName=name)
    else:
        log.warning(f"stack not found {name}")
    show.callback()


@c.command(help="show aws resources currently used")
def show():
    """show aws resources currently used"""
    u.show()
