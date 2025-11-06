"""OAuth Token Repository（OAuth令牌数据访问层）

职责：
- 封装 OAuth token 相关的数据库查询操作
- 根据 athlete_id 获取对应的 access_token
"""

from typing import Optional
from sqlalchemy.orm import Session
import logging
import requests
from datetime import datetime, timedelta

from ..db.models import TbDevice, TbOauthToken

logger = logging.getLogger(__name__)


def get_access_token_by_athlete_id(db: Session, athlete_id: int) -> Optional[str]:
    try:
        # 步骤1: 根据 athlete_id 查找对应的 device
        device = db.query(TbDevice).filter(TbDevice.owner_id == athlete_id).first()
        
        # 步骤2: 根据 device_id 查找对应的 oauth_token
        oauth_token = db.query(TbOauthToken).filter(TbOauthToken.device_id == device.id).first()
        
        # 步骤3: 检查 token 是否过期（通过调用 Strava API 验证）
        try:
            if oauth_token.update_time < datetime.now() - timedelta(seconds = 21600):
                client_id = "142151"
                client_secret = "6cb6c2d067e891eaba1850fc2c9b0631e3c32e7c"
                refresh_url = "https://www.strava.com/oauth/token"
                refresh_data = {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": oauth_token.refresh_token,
                }
                refresh_response = requests.post(refresh_url, data=refresh_data, timeout=5)
                refresh_result = refresh_response.json()
                # 更新数据库中的 access_token
                oauth_token.access_token = refresh_result.get("access_token")
                oauth_token.update_time = datetime.now()
                db.commit()
                
        except Exception as e:
            db.rollback()
            logger.exception("[oauth-repo][error] athlete_id=%s err=%s",athlete_id,e)
            return None
        return oauth_token.access_token
        
    except Exception as e:
        logger.exception("[oauth-repo][error] athlete_id=%s err=%s",athlete_id,e)
        return None


