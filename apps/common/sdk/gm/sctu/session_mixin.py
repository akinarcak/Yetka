from ctypes import *

from common.sdk.gm.base.exception import GMDeviceError
from common.sdk.gm.base.session_mixin import BaseMixin


def as_uchar_array(data: bytes):
    return (c_ubyte * len(data))(*data)


class SM4Mixin(BaseMixin):

    ## 此处不导入 key
    def import_key(self, key_val):
        pass

    def destroy_cipher_key(self, key):
        pass

    def encrypt(self, plain_text, key, alg, iv=None):
        return self.__do_cipher_action(plain_text, key, alg, iv, True)

    def decrypt(self, cipher_text, key, alg, iv=None):
        return self.__do_cipher_action(cipher_text, key, alg, iv, False)

    def __do_cipher_action(self, text, key, alg, iv=None, encrypt=True):
        text = (c_ubyte * len(text))(*text)
        if iv is not None:
            iv = (c_ubyte * len(iv))(*iv)

        temp_data = (c_ubyte * len(text))()
        temp_data_length = c_int()

        ## 这里的 key 不是指针而是明文

        key_arr = as_uchar_array(key)

        if encrypt:
            ret = self._driver.HS_SDF_Encrypt(self._session,
                                              key_arr,
                                              c_int(len(key_arr)),
                                              0,
                                              c_int(alg),
                                              iv,
                                              text,
                                              c_int(len(text)),
                                              temp_data,
                                              pointer(temp_data_length))
            if ret != 0:
                raise GMDeviceError("encrypt failed", ret)
        else:
            ret = self._driver.HS_SDF_Decrypt(self._session,
                                              key_arr,
                                              c_int(len(key_arr)),
                                              0,
                                              c_int(alg),
                                              iv,
                                              text,
                                              c_int(len(text)),
                                              temp_data,
                                              pointer(temp_data_length))
            if ret != 0:
                raise GMDeviceError("decrypt failed", ret)
        return temp_data[:temp_data_length.value]
