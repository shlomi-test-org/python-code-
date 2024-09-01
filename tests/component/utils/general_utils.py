from typing import Dict


def compare_first_dict_in_second(dict1: Dict, dict2: Dict):
    """
    This takes dict 1, and checks if it's contained in dict 2, including one nested level.
    All None values from dict 1 are ignored.
    example:
    dict1:
    {
       "key1": "123",
       "key2": None,
       "key3": {
          "sub1": "1",
          "sub2": None
       }
    }
    will be true for:
    dict1:
    {
       "key1": "123",
       "aditional": "124312412"
       "key3": {
          "sub1": "1",
       }
    }
    """
    for key in dict1:
        val = dict1[key]
        if val is not None:
            if isinstance(val, dict):
                for k in val:
                    if val[k] is not None:
                        assert val[k] == dict2[key][k]
            else:
                assert dict1[key] == dict2[key]
