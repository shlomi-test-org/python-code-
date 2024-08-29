from typing import Dict
from typing import Optional

from jit_utils.logger import logger
from pydantic import BaseModel

from src.lib.helpers import parse_jsonpath


class PricingMapper(BaseModel):
    name: str
    product_sku: str
    terms_sku: str
    required_unit: Optional[str]
    free_amount: Optional[int] = 0

    def get_price(self, aws_price_data: Dict) -> Optional[float]:
        base_path = (
            f'$.terms.OnDemand[?(@.sku == "{self.product_sku}")].'
            f'priceDimensions[?(@.rateCode == "{self.terms_sku}")]'
        )
        price = parse_jsonpath(f"{base_path}.pricePerUnit.USD", aws_price_data)
        if not price:
            return None
        if self.required_unit:
            unit_value = parse_jsonpath(f"{base_path}.unit", aws_price_data)
            if not unit_value or unit_value != self.required_unit:
                logger.warning(
                    f"{base_path}.unit of {unit_value} is not equal to requested {self.required_unit}"
                )
                return None
        return float(price)


# Prices calculation consts
LINUX_X86_CALCULATION = (
    "([billable_duration_minutes] / 60) * "
    "([vcpu] * <Linux/X86 per vCPU per hour> + [memory_gb] * <Linux/X86 per GB per hour>)"
)
LINUX_ARM_CALCULATION = (
    "([billable_duration_minutes] / 60) * "
    "([vcpu] * <Linux/ARM per vCPU per hour> + [memory_gb] * <Linux/ARM per GB per hour>)"
)
WINDOWS_CALCULATION = (
    "([billable_duration_minutes] / 60) * "
    "([vcpu] * (<Windows/X86 per vCPU per hour> + "
    "<Windows/X86 OS license fee - per vCPU per hour>) +"
    " [memory_gb] * <Windows/X86 per GB per hour>)"
)
STORAGE_CALCULATION = "[billable_storage_gb] * <per storage GB per hour>"

PRICE_STORAGE = "per storage GB per hour"
PRICE_LINUX_X86_VCPU = "Linux/X86 per vCPU per hour"
PRICE_LINUX_X86_MEMORY = "Linux/X86 per GB per hour"
PRICE_LINUX_ARM_VCPU = "Linux/ARM per vCPU per hour"
PRICE_LINUX_ARM_MEMORY = "Linux/ARM per GB per hour"
PRICE_WINDOWS_X86_VCPU = "Windows/X86 per vCPU per hour"
PRICE_WINDOWS_X86_MEMORY = "Windows/X86 per GB per hour"
PRICE_WINDOWS_X86_LICENSE = "Windows/X86 OS license fee - per vCPU per hour"

PRICING_DEFAULTS = {
    PRICE_STORAGE: 0.000111,
    PRICE_LINUX_X86_VCPU: 0.04048,
    PRICE_LINUX_X86_MEMORY: 0.004445,
    PRICE_LINUX_ARM_VCPU: 0.03238,
    PRICE_LINUX_ARM_MEMORY: 0.00356,
    PRICE_WINDOWS_X86_VCPU: 0.09148,
    PRICE_WINDOWS_X86_MEMORY: 0.01005,
    PRICE_WINDOWS_X86_LICENSE: 0.046,
}

# SKU will always be product.sku (key of the mapping)
SKU_TO_PRICING_MAPPING = {
    "7KPDPTDSCT4J3Z64": PricingMapper(
        name=PRICE_STORAGE,
        product_sku="7KPDPTDSCT4J3Z64",
        terms_sku="7KPDPTDSCT4J3Z64.JRTCKXETXF.6YS6EN2CT7",
        unit="GB-Hours",
        free_amount=20,
    ),
    "8CESGAFWKAJ98PME": PricingMapper(
        name=PRICE_LINUX_X86_VCPU,
        product_sku="8CESGAFWKAJ98PME",
        terms_sku="8CESGAFWKAJ98PME.JRTCKXETXF.6YS6EN2CT7",
        unit="hours",
    ),
    "8QDMJPGQCM368Z6X": PricingMapper(
        name=PRICE_WINDOWS_X86_MEMORY,
        product_sku="8QDMJPGQCM368Z6X",
        terms_sku="8QDMJPGQCM368Z6X.JRTCKXETXF.6YS6EN2CT7",
        unit="hours",
    ),
    "RF2BUTAD289DREDC": PricingMapper(
        name=PRICE_WINDOWS_X86_VCPU,
        product_sku="RF2BUTAD289DREDC",
        terms_sku="RF2BUTAD289DREDC.JRTCKXETXF.6YS6EN2CT7",
        unit="hours",
    ),
    "9D3ZWXRS2VXMZET6": PricingMapper(
        name="Windows/X86 OS license fee - per vCPU per hour",
        product_sku="9D3ZWXRS2VXMZET6",
        terms_sku="9D3ZWXRS2VXMZET6.JRTCKXETXF.6YS6EN2CT7",
        unit="hours",
    ),
    "PBZNQUSEXZUC34C9": PricingMapper(
        name=PRICE_LINUX_X86_MEMORY,
        product_sku="PBZNQUSEXZUC34C9",
        terms_sku="PBZNQUSEXZUC34C9.JRTCKXETXF.6YS6EN2CT7",
        unit="hours",
    ),
    "UNH9KPQP7W7C66C9": PricingMapper(
        name=PRICE_LINUX_ARM_MEMORY,
        product_sku="UNH9KPQP7W7C66C9",
        terms_sku="UNH9KPQP7W7C66C9.JRTCKXETXF.6YS6EN2CT7",
        unit="hours",
    ),
    "XSZATS4VYMDC9CYN": PricingMapper(
        name=PRICE_LINUX_ARM_VCPU,
        product_sku="XSZATS4VYMDC9CYN",
        terms_sku="XSZATS4VYMDC9CYN.JRTCKXETXF.6YS6EN2CT7",
        unit="hours",
    ),
}
