from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response

from common.permissions import OnlySuperUser
from common.jdmc import request_jdmc
from common.utils import get_logger


__all__ = ['JdmcSSOTokenAPI']


logger = get_logger(__file__)


class JdmcSSOTokenAPI(RetrieveAPIView):

    permission_classes = [OnlySuperUser]

    def retrieve(self, request, *args, **kwargs):
        logger.info(f'User {request.user.username} is requesting JDMC SSO token')
        token, error = self.create_sso_token()
        if error:
            return Response({'error': error}, status=403)
        else:
            return Response({'token': token})

    def create_sso_token(self):
        response = request_jdmc(method='POST', path='/jdmc/api/v1/auth/tokens')

        if response.status_code != 200:
            error = f'Failed to create SSO token from JDMC, status code: {response.status_code}, response: {response.text}'
            logger.error(error)
            return None, error

        json_response = response.json()
        if json_response.get('code') != 0:
            error = f'Failed to create SSO token from JDMC, response: {json_response}'
            logger.error(error)
            return None, error
        
        token = json_response.get('data', {}).get('token', '')
        return token, ''
