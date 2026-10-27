"""Constants for the Yasno outages integration."""

DOMAIN = "yasno"

CONF_REGION_ID = "region_id"
CONF_REGION = "region"
CONF_DSO_ID = "dso_id"
CONF_DSO = "dso"
CONF_STREET_ID = "street_id"
CONF_STREET = "street"
CONF_HOUSE_ID = "house_id"
CONF_HOUSE = "house"
CONF_GROUP = "group"

FETCH_SECONDS = 10 * 60  # how often the schedule is read from Yasno
PROBABLE_FETCH_SECONDS = 3600  # the weekly probable schedule
GROUP_CHECK_SECONDS = 24 * 3600  # how often the address is looked up again (groups get reassigned)
FAR_MINUTES = 9999  # "minutes to outage" when none is scheduled
