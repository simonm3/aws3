import logging
import os
import random
from base64 import b64encode

import click
import yaml
from defaultlog import log

for logger in ["botocore", "numexpr"]:
    logging.getLogger(logger).setLevel(logging.WARNING)

from . import utils as u
from .utils import cf, ec2


class OrderCommands(click.Group):
    """make help message show commands in order defined not alphabetical"""

    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands)


@click.group(cls=OrderCommands)
def c():
    """simplified cli for aws stacks"""
    pass


@c.command()
@click.argument("template")
@click.argument("name", default="", required=False)
def start(template, name=""):
    """start stack from template name. adds .yaml (template) and .sh (startup script)"""
    params = dict()

    # get template
    base, ext = os.path.splitext(template)
    if not ext and not os.path.isfile(template):
        template = f"{base}.yaml"
    stack = yaml.safe_load(open(template).read())

    if name:
        tname = u.tag(name)
        # existing image
        images = u.get_images(**u.tag(name=name))
        if images:
            params["ImageId"] = images[-1].id
    else:
        # new image
        here = os.path.dirname(os.path.abspath(__file__))
        with open(f"{here}/names.csv") as f:
            names = f.read().split("\n")
        # avoid existing images
        images = u.get_images(**u.tag(name=name))
        names = list(set(names) - set(images))
        name = random.choice(names)

    # launch
    params["Name"] = name
    log.info(f"launching {name} with template {template}")
    res = cf.create_stack(
        StackName=name,
        TemplateBody=yaml.dump(stack),
        Parameters=u.params(**params),
    )


@c.command()
@click.argument("name")
def terminate(name):
    """delete stack with name"""
    log.info(f"terminating {name}")
    cf.delete_stack(StackName=name)
    show.callback()


@c.command()
@click.argument("name")
def stop(name):
    """create image and stop stack with name"""
    tname = u.tag(name)

    # get instance
    InstanceId = u.get_instances(**u.tag(name=name))[0]["InstanceId"]

    # create image
    log.info(f"saving image {name}")
    r = ec2.create_image(
        InstanceId=InstanceId,
        Name=name,
        TagSpecifications=[
            dict(ResourceType="image", Tags=u.tags(name=name)),
            dict(ResourceType="snapshot", Tags=u.tags(name=name)),
        ],
    )
    # remove old images
    log.info(f"removing old images {name}")
    images = u.get_images(**u.tag(name=name))
    for image in images[:-1]:
        ec2.deregister_image(ImageId=image.id)

    log.info(f"removing stack {name}")
    waiter = ec2.get_waiter("image_available")
    waiter.wait(ImageIds=[r["ImageId"]])
    cf.delete_stack(StackName=name)

    show.callback()


@c.command()
def show():
    u.show()
