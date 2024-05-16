"""
aws utility functions
    convert dicts to aws formats and vice versa
    list resources
    get instance information
"""
import itertools
import json
import logging
import re
from datetime import datetime

import boto3
import pandas as pd

log = logging.getLogger(__name__)

ec2 = boto3.client("ec2")
cf = boto3.client("cloudformation")

# dict2aws ###########################################


def filters(**kwargs):
    """format dict into filter format
    e.g. filt(a=b) => [dict(Name="a", Values=["b"]]
    """
    # replace _ to allow use of dict() rather than {}
    return [dict(Name=k.replace("_", "-"), Values=[v]) for k, v in kwargs.items()]


def tags(**kwargs):
    return [dict(Key=k, Value=v) for k, v in kwargs.items()]


def params(**kwargs):
    return [dict(ParameterKey=k, ParameterValue=v) for k, v in kwargs.items()]


def tag(**kwargs):
    """apply search filters to tags"""
    return {f"tag:{k}": v for k, v in kwargs.items()}


# aws2dict ###################################################


def get_tags(res):
    if "Tags" in res:
        return {tag["Key"]: tag["Value"] for tag in res["Tags"]}
    return {}


# list live resources ###############################


def get_instances(**kwargs):
    try:
        r = ec2.describe_instances(Filters=filters(**kwargs))["Reservations"][0][
            "Instances"
        ]
    except IndexError:
        return []
    return sorted(r, key=lambda s: s["LaunchTime"])


def get_images(**kwargs):
    r = ec2.describe_images(Filters=filters(**kwargs), Owners=["self"])["Images"]
    return sorted(r, key=lambda s: s["CreationDate"])


def get_volumes(**kwargs):
    r = ec2.describe_volumes(Filters=filters(**kwargs))["Volumes"]
    return sorted(r, key=lambda s: s["CreateTime"])


def get_snapshots(**kwargs):
    r = ec2.describe_snapshots(Filters=filters(**kwargs), OwnerIds=["self"])[
        "Snapshots"
    ]
    return sorted(r, key=lambda s: s["StartTime"])


def get_ips():
    """get list of elastic ips"""
    return [ip["PublicIp"] for ip in ec2.describe_addresses()["Addresses"]]


def get_stacks(**kwargs):
    r = cf.list_stacks(StackStatusFilter=["CREATE_COMPLETE"])["StackSummaries"]
    return sorted(r, key=lambda s: s["CreationTime"])


def show():
    """list names of live resources"""
    instances = [
        get_tags(x).get("Name", "unknown")
        for x in get_instances(instance_state_name="running")
    ]
    images = [get_tags(x).get("Name", "unknown") for x in get_images()]
    # TODO state in ['creating','available','in-use']
    volumes = [get_tags(x).get("Name", "unknown") for x in get_volumes()]
    snapshots = [get_tags(x).get("Name", "unknown") for x in get_snapshots()]
    stacks = [x["StackName"] for x in get_stacks()]
    log.info(f"{instances=}\n{images=}\n{volumes=}\n{snapshots=}\n{stacks=}")

    log.info(
        f"\ninstances={len(instances)}; images={len(get_images())}; volumes={len(get_volumes())};"
        f"snapshots={len(get_snapshots())}; stacks={len(get_stacks())}"
    )


# get dataframe of instances ######################


def get_instancesdf(**filters):
    """return dataframe of instances"""
    from . import Instance

    alldata = []
    for i in get_instances(**filters):
        i = Instance(i)
        data = dict(
            name=i.name,
            instance_id=i.instance_id,
            image=i.image_id,
            type=i.instance_type,
            state=i.state["Name"],
            ip=i.public_ip_address,
        )
        tags = i.tags
        tags.pop("Name", None)
        data.update(tags)

        alldata.append(data)
    # fillna for the tags
    return pd.DataFrame(alldata).fillna("")


def get_instancetypes():
    """return dataframe of instance types/features available in EU"""
    # API only available in specific regions
    pricing = boto3.client("pricing", "us-east-1")

    pager = pricing.get_paginator("get_products").paginate(
        ServiceCode="AmazonEC2",
        Filters=[
            dict(Type="TERM_MATCH", Field="location", Value="EU (Ireland)"),
            dict(Type="TERM_MATCH", Field="tenancy", Value="Shared"),
            dict(Type="TERM_MATCH", Field="operatingSystem", Value="Linux"),
        ],
        PaginationConfig=dict(MaxItems=1e4),
    )
    pages = [page["PriceList"] for page in pager]
    products = list(itertools.chain.from_iterable(pages))
    attribs = [json.loads(v)["product"]["attributes"] for v in products]
    df = pd.DataFrame(attribs)
    df.columns = standardise(df.columns)
    df = df.loc[df.instance_type.notnull()]
    df.gpu = df.gpu.fillna(0).astype(int)
    df.vcpu = df.vcpu.fillna(0).astype(int)
    df.memory = (
        df.memory.str.replace(",", "")
        .str.extract("(\d+)", expand=False)
        .fillna(0)
        .astype(int)
    )
    df = df[df.memory > 0].drop_duplicates(["instance_type"])

    return df


def get_spotprices():
    """return dataframe of spot prices

    standardised columns available for query/sort::

    clock_speed, current_generation, dedicated_ebs_throughput, ecu, enhanced_networking_supported, gpu, instance_family, instance_type, intel_avx2available, intel_avx_available, intel_turbo_available, license_model, location, location_type, memory, network_performance, normalization_size_factor, operating_system, operation, physical_processor, pre_installed_sw, processor_architecture, processor_features, servicecode, servicename, storage, tenancy, usagetype, vcpu, availability_zone, spot_price, percpu, per64cpu
    """

    itypes = get_instancetypes()

    # get current spot prices
    pager = ec2.get_paginator("describe_spot_price_history").paginate(
        StartTime=f"{datetime.utcnow()}Z",
        ProductDescriptions=["Linux/UNIX"],
        PaginationConfig=dict(MaxItems=1e4),
    )
    pages = [page["SpotPriceHistory"] for page in pager]
    pages = list(itertools.chain.from_iterable(pages))
    prices = pd.DataFrame(pages)
    prices.columns = standardise(prices.columns)
    prices = prices[["availability_zone", "instance_type", "spot_price"]]
    prices.spot_price = prices.spot_price.astype(float)

    # merge
    merged = itypes.merge(prices, on="instance_type", how="inner")
    merged["percpu"] = merged.spot_price / merged.vcpu
    merged["per64cpu"] = merged.percpu * 64
    return merged.sort_values("percpu")


def standardise(names):
    """pep8 names
    :return: list of names that are underscore separated and lower case
    """
    names = [x.strip() for x in names]
    # camelCase to underscore separated
    names = [re.sub("([a-z]+)([A-Z])", r"\1_\2", x) for x in names]
    # non-alphanumeric to underscore
    names = [re.sub("\W+", "_", x) for x in names]
    names = [x.lower() for x in names]
    return names
