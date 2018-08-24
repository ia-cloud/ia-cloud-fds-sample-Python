# -*- coding:utf-8 -*-
'''
ia-cloud CCS interface module, which privides functionarity of
ia-cloud command APIs including connect, sore, retrieve ,getStatus
and terminate.

 Usage:
 	Put this file in ia_cloud directory right under your working Dir.
 	from ia_cloud.ia_cloud_connection import IaCloudConnection, CCSBadResponseError

Attributes: String mssages of CCS response json
	GOOD = "ok"
	NG = "ng"
	DISCONNECTED = "disconnected"
'''

import datetime
# Python組込のデータコンテナに変わるコンテナのパッケージ OrderedDictを利用
from collections import OrderedDict
#jsonのパッケージ
import json

# Httpリクエストを利用するパッケージ
import requests
# requestsモジュールの例外の定義をインポート
from requests.exceptions import ConnectionError, Timeout, HTTPError
from requests.auth import HTTPBasicAuth

# CCSレスポンス定数定義
GOOD = "ok"
NG = "ng"
DISCONNECTED = "disconnected"

#-------------------------------------------------------
# CCSからのレスポンスボディのJSONが不正な場合のエラー
#-------------------------------------------------------
class CCSBadResponseError(Exception):
	'''
	A Exception which related to ia-cloud API level CCS response error, like,
	CCS responds the response baody with invalid jason value or key,
	CCS dose not provide a valid serviceID

	Usage:
		except CCSBadResponseError as err:
			logger.error(err)
	'''
	def __init__(self, res_data: dict, message: str):
		self.res_data = res_data
		self.message = message

	def __str__(self) :
		return("Error massage:{0}\n　response data :{1}".format(
											self.message, self.res_data))

#-------------------------------------------------------
# ia-cloud_connection クラスの定義
#-------------------------------------------------------
class IaCloudConnection(object):
	'''
	A ia-cloud CCS connection class which provides ia-cloud REST JSON APIs

	Usage:
		iac_con = IaCloudConnection(con_info, options)

		iac_con.connect()
		iac_con.sotr(store_obj)
				.
				.
				.
	'''
	#-------------------------------------------------------
	# 初期化　コンストラクター
	#-------------------------------------------------------
	def __init__(self, connection_info:OrderedDict,
				options:OrderedDict):
		'''
		The constructor of class IaCloudConnection

		Usage:
			iac_con = IaCloudConnection(con_info, options)

		Args:
			connectiopn_info(OrderedDict):
				Connecting information between FDS and CCS, like
				CCS url, userID ,password, FDSKey..... in OrderedDict
			options(dict):
				Optional information regarding CCS connection, like
				proxies, retries, timezone...... in dict

		    These Args might be provided by the following JSON expression

			"iaCloudConfig":{
				"userID": "username",
				"password": "password",
				"FDSKey": "com.exsample.raspberrypi-1",
				"FDSType": "iaCloudFDS",
				"comment": "ia-cloud Sample Application for RaspberryPi",
				"requestUrl": "https://example.com/iaCloud/rev100",
				"options": {
					"logName": "iaCloud",
					"httpTimeout": [10,30],
					"httpRetry": 2,
					"proxies": {"https": "http://example:8080"},
					"timezone":"JST",
					"errorValue": null,
					"debug": true,
					"objects": ["p_CPUTemp", "p_GPIO", "a_GPIO40_on", "a_GPIO40_off"]
				}
		'''
		# ia-cloudCCSへの接続情報をセット
		self.con_info = connection_info

		# ia-cloud接続情報オブジェクトからoptions情報を削除して内部オブジェクトに取り出し
		self.options = options

		# タイムゾーンを設定（JSTとUTCのみをサポート）
		if  self.options["timezone"] == "JST":
			self.tz = datetime.timezone(
				datetime.timedelta(hours=+9),'JST')
		else :
			self.tz = datetime.timezone(
				datetime.timedelta(hours=+0), 'UTC')

		# HTTPリクエストのセッションを生成.
		self.session = requests.Session()

		# Request アダプターをマウント
		self.session.mount("https://",
				requests.adapters.HTTPAdapter(
					pool_connections = 10,
					pool_maxsize = 10,
					max_retries=self.options["httpRetry"]
					)
				)
		# Httpリクエストパラメータを設定
		self.session.headers = {"content-type": "application/json"}
		self.session.auth = HTTPBasicAuth(
			self.con_info["userID"],self.con_info["password"])
		proxies = self.options["proxies"]
		self.session.proxies = proxies\
			if proxies != {"https": "http://example:8080"} else None
		self.session.timeout = self.options["httpTimeout"]

	#-------------------------------------------------------
	# CCSへPOSTリクエストをする内部メソッド
	#-------------------------------------------------------
	def _POST_request(self, req_data: OrderedDict) :

		try:
			# リクエストデータをJSONにエンコード
			data=json.dumps(req_data)
			# Httpリクエストを送出
			resp = self.session.post(
				self.con_info["requestUrl"], data=data,
				headers = {"content-type": "application/json"}
				)
			# レスポンスコードが200以外は例外を送出
			resp.raise_for_status()

		# requests関連の例外はそのままraise
		except ConnectionError:
			raise

		except HTTPError:
			raise

		except Timeout:
			raise
		else:
			# レスポンスボディのjsonをdictにパースしてreturn
			return json.loads(resp.text)

	#-------------------------------------------------------
	# CCSとのia-cloud接続を開始するメソッド
	#-------------------------------------------------------
	def connect(self):
		'''
		A connect method to establish new CCS connection using connection
		information which is provided by constructor.
		Set serveID recieved from CCS to Self.con_info["serviceID"]

		Usage:
			iac_con = IaCloudConnection(con_info, options)
			iac_con.connect()
		Returns:
			res_data(dict):dict data decoded from JSON response body
		'''
		# リクエストデータの作成
		req_data = OrderedDict((
			("request", "connect"),
			("userID", self.con_info["userID"]),
			("FDSKey", self.con_info["FDSKey"]),
			("FDSType", self.con_info["FDSType"]),
			("timeStamp", datetime.datetime.now(self.tz).isoformat('T')),
			("comment", self.con_info["comment"])
			))

		# リクエストデータの送出
		try:
			res_data = self._POST_request(req_data)

		# http以下のレイヤーのエラーが発生したらそのままraise
		except :
			raise


		try:
			# レスポンスデータの確認
			# レスポンスデータが不正なら例外を発生
			if	res_data["userID"] != req_data["userID"] or\
				res_data["FDSKey"] != req_data["FDSKey"] or\
				res_data["FDSType"] != req_data["FDSType"] :

				raise CCSBadResponseError(
					res_data=res_data, message="Bad JSON response")

		except KeyError as err:
			raise CCSBadResponseError(
					res_data=res_data,
					message="Bad JSON response with KeyError")

		else:
			# レスポンスデータからserviceIDを更新
			if "serviceID" not in res_data:
				raise CCSBadResponseError(res_data=res_data,
						message="serviceID not provided")

			else:
				self.con_info["serviceID"] = res_data["serviceID"]

		return res_data

	#--------------------------------------------------------
	# ia-cloudのオブジェクトのストアメソッド
	#--------------------------------------------------------
	def store(self, sobject: OrderedDict):
		'''
		A method to store data object into the connected CCS.
		Set newserveID recieved from CCS to Self.con_info["serviceID"]

		Usage:
			iac_con = IaCloudConnection(con_info, options)
			iac_con.stire(store_obj)
		Args:
			store=obj(OrderedDict):object data that would be sent to CCS.
		Returns:
			res_data(dict):dict data decoded from JSON response body
		'''

		# リクエストデータの作成
		req_data = OrderedDict(
				(("request", "store"),
				("serviceID", self.con_info["serviceID"]))
				)
		req_data["dataObject"] = sobject

		# リクエストデータの送出
		try:
			res_data = self._POST_request(req_data)

		# http以下のレイヤーのエラーが発生したらそのままraise
		except :
			raise

		try:
			# レスポンスデータの確認
			# レスポンスデータが不正なら例外を発生
			if	res_data["serviceID"] != req_data["serviceID"] or\
				res_data["status"].lower() != GOOD :

				raise CCSBadResponseError(
					res_data=res_data, message="Bad JSON response")

		except KeyError as err:
			raise CCSBadResponseError(
					res_data=res_data,
					message="Bad JSON response with KeyError")

		else:
			# レスポンスデータからserviceIDを更新
			if "newServiceID" not in res_data:
				raise CCSBadResponseError(res_data=res_data,
							message="serviceID not provided")
			else:
				self.con_info["serviceID"] = res_data["newServiceID"]

		return res_data

	#--------------------------------------------------------
	# ia-cloudのオブジェクトのリトリーブメソッド
	#--------------------------------------------------------
	def retrieve(self, robject:OrderedDict):
		'''
		A method to retrieve data object from the connected CCS.
		Set newserveID recieved from CCS to Self.con_info["serviceID"]

		Usage:
			iac_con = IaCloudConnection(con_info, options)
			iac_con.retrieve()
		Args:
			retrieve_obj(dict):timeStamp, objectKey or instanceKey of data object
			to be retrieved in dict.
		Returns:
			retrieved_obj(dict): data object retrieved from CCS.
		'''
		# リクエストデータの作成
		req_data = OrderedDict((
					("request", "retieve"),
					("serviceID", self.con_info["serviceID"])
					))
		req_data["retrieveObject"] = robject

		# リクエストデータの送出
		try:
			res_data = self._POST_request(req_data)

		# http以下のレイヤーのエラーが発生したらそのままraise
		except :
			raise

		try:
			# レスポンスデータの確認
			# レスポンスデータが不正なら例外を発生
			if	res_data["serviceID"] != req_data["serviceID"] or\
				res_data["status"].lower() != GOOD :

				raise CCSBadResponseError(
					res_data=res_data, message="Bad JSON response")

		except KeyError as err:
			raise CCSBadResponseError(
					res_data=res_data,
					message="Bad JSON response with KeyError")

		else:
			# レスポンスデータからserviceIDを更新
			if "newServiceID" not in res_data:
				raise CCSBadResponseError(res_data=res_data,
						message="serviceID not provided")
			else:
				self.con_info["serviceID"] = res_data.pop("newServiceID")

		return res_data["dataObject"]

	#--------------------------------------------------------
	# ia-cloudのオブジェクトのserviceID更新メソッド
	#--------------------------------------------------------
	def get_status(self):
		'''
		A method to request new serviceID to the connected CCS.
		Set newserveID recieved from CCS to Self.con_info["serviceID"]
		CCS could provide same serviceID as currently used.

		Usage:
			iac_con = IaCloudConnection(con_info, options)
			iac_con.get_status()

		Returns:
			res_data(dict):dict data decoded from JSON response body	.
		'''
		# リクエストデータの作成
		req_data = OrderedDict((
					("request", "getStaus"),
					("serviceID", self.con_info["serviceID"]),
					("timeStamp", datetime.datetime.now(self.tz).isoformat('T')),
					))

		# リクエストデータの送出
		try:
			res_data = self._POST_request(req_data)

		# http以下のレイヤーのエラーが発生したらそのままraise
		except :
			raise

		try:
			# レスポンスデータの確認
			# レスポンスデータが不正なら例外を発生
			if	res_data["FDSKey"] != self.con_info["FDSKey"] or\
				res_data["oldServiceID"] != req_data["serviceID"] :


				raise CCSBadResponseError(
					res_data=res_data, message="Bad JSON response")

		except KeyError as err:
			raise CCSBadResponseError(
					res_data=res_data,
					message="Bad JSON response with KeyError")

		# レスポンスデータからserviceIDを更新
		else:
			if "newServiceID" not in res_data:
				raise CCSBadResponseError(res_data=res_data,
							message="serviceID not provided")
			else:
				self.con_info["serviceID"] = res_data["newServiceID"]

		return res_data

	#--------------------------------------------------------
	# ia-cloudのオブジェクトの接続の終了メソッド
	#--------------------------------------------------------
	def terminate(self):
		'''
		A method to terminate CCS connection.

		Usage:
			iac_con = IaCloudConnection(con_info, options)
			iac_con.terminate()

		Returns:
			res_data(dict):dict data decoded from JSON response body.
		'''

		req_data = OrderedDict((
			("request", "terminate"),
			("serviceID", self.con_info["serviceID"])
			))

		# リクエストデータの送出
		try:
			res_data = self._POST_request(req_data)

		# http以下のレイヤーのエラーが発生したらそのままraise
		except :
			raise

		try:
			# レスポンスデータの確認
			# レスポンスデータが不正なら例外を発生
			if res_data["serviceID"] != req_data["serviceID"] or \
			 	res_data["message"] != DISCONNECTED:

				raise CCSBadResponseError(
					res_data=res_data, message="Bad JSON response")

		except KeyError as err:
			raise CCSBadResponseError(
					res_data=res_data,
					message="Bad JSON response with KeyError")

		# serviceIDを削除する
		else:
			del self.con_info["serviceID"]

		return res_data
