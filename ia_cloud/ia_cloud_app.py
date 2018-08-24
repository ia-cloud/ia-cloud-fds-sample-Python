# -*- coding:utf-8 -*-
'''
ia-cloud application module including a application class.

Usage:
	Put this file in ia_cloud directory right under your working Dir.
	from ia_cloud.ia_cloud_app import IaCloudApp
	ia_cloud_connection.py must exist in the directory ia_cloud, also.

Attributes: Application log configuration
	MAXLOGSIZE: Maximan saize of log file.
	LOGROTATION: number of log rotation file.
'''
import copy
import time
import datetime
#from threading import Event, Threadt
import threading
#jsonのパッケージ
import json
# Python組込のデータコンテナに変わるコンテナのパッケージ OrderedDictを利用
from collections import OrderedDict
# Shellコマンドを呼び出すパッケージ
import subprocess
# シグナルをハンドルするパッケージ
import signal
# ログパッケージ
import logging
import logging.handlers

# requestsモジュールの例外の定義をインポート
from requests.exceptions import ConnectionError, HTTPError, Timeout

# ia_cloud_connectionモジュールをインポート
from ia_cloud.ia_cloud_connection import IaCloudConnection, CCSBadResponseError

MAXLOGSIZE = 500000
LOGROTATION = 5
#-------------------------------------------------------
# ia-cloudアプリケーションクラスの定義
# 必要に応じてサブクラスで、
# 非同期データ収集のスレッドを起動するメソッドを定義し、
# 格納すべきデータを取得するメソッドをオーバーライド定義し使用する。
#-------------------------------------------------------
class IaCloudApp(object):
	'''
	A ia-cloud application :class: which provides ia-cloud FDS functionality.

	Usage:
		iac_app = IaCloudApp(FDS_config)
		iac_app.start()
		async_trigger(obj_name)
	'''
	#-------------------------------------------------------
	# 初期化　コンストラクター
	#-------------------------------------------------------
	def __init__(self, FDS_config:OrderedDict):
		'''
		The constructor of class IaCloudApp

		Usage:
			iac_con = iaCloudCApp(FDS_config)

			Args:
			FDS_config(OrderedDict):
			FDS configuration consists of iaCloudConfig and object_confs.
			These information would be provided with JSON file. A example
			configuration JSON file is in the same pakage ia_cloud and named
			"ia_cloud_config.json"
		'''
		#各種設定情報を引数のFDS_configから取得
		self.con_info = FDS_config.pop("iaCloudConfig")
		# ia-cloud接続情報オブジェクトからoptions情報を削除して内部オブジェクトに取り出し
		self.options = self.con_info.pop("options")
		# option情報のデバッグフラグをセット
		self.debug = self.options["debug"]

		# loggerのインスタンスを作成
		self.logger = self._createlogger(self.options["logName"])
		# アプリケーション開始のメッセージをログ出力
		self.logger.info("IaCloudApp is started")

		# タイムゾーンを設定（JSTとUTCのみをサポート）
		if  self.options["timezone"] == "JST":
			self.tz = datetime.timezone(
				datetime.timedelta(hours=+9),'JST')
		else :
			self.tz = datetime.timezone(
				datetime.timedelta(hours=+0), 'UTC')

    	# 対象のia-cloudオブジェクトの設定情報をセット
		# "iaCloudConfig"は、popされてobject_confsだけが残っている
		self.object_confs = FDS_config
		# データ収集スレッドへ終了を伝えるイベントを作成
		self.event = threading.Event()

		#ia-cloud CCSへの接続オブジェクトを生成
		self.iac_con = IaCloudConnection(self.con_info, self.options)

		for i in range(3):
			try:
				#IAクラウドCCSへの接続のリクエスト
				res_data = self.iac_con.connect()
			# HTTP関連エラーやCCSが不正レスポンスを返した場合
			except (CCSBadResponseError,
					ConnectionError, HTTPError, Timeout) as err:

				# メッセージ出力し
				msg = "CCS Invalid Response or Http Error on connect."
				self.logger.error(msg)
				self.logger.debug(err)
				self.logger.debug(json.dumps(self.con_info))
				self.logger.debug(json.dumps(self.options))
			else:
				# 接続が成功したらログの出力
				self.logger.info("connected to CCS")
				self.logger.debug(json.dumps(self.con_info))

				# 収集オブジェクトごとに処理するスレッドを入れる辞書を作成
				self.acq_th = {}
				break

		#　リトライしても繋がらない
		if i == 2:
			# コネクトリクエストでリトライアウトのメセージをログ出力
			msg =("CCS connect request has been retried out. ")
			self.logger.error(msg)
			# mainスレッドに通知アラーム発信、ハンドラーの処理を待つ
			signal.alarm(1)
			while True:
				time.sleep(1)

	#-------------------------------------------------------
	# すべてのデータ収集スレッドを停止し、CCSとのコネネクションを終了するメソッド
	#-------------------------------------------------------
	def stop(self):
		'''
		A method to terminate the application class instance.
		This method set event to terminate all existing threads working on data
		acquisition, and communication with CCS.

		Usage:
			iac_app = iaCloudCApp(FDS_config)
			iac_app.stop()
		'''

		# 収集のスレッドリストがからでなければ
		if len(self.acq_th) > 0:

			# スレッドを停止するEventをセット
			self.event.set()

			# すべてのデータ収集スレッドの終了を確認
			while True :
				for th in self.acq_th:
					if self.acq_th[th].is_alive():
						continue
				break

		# CCSへの接続はあるか？　serviceIDでチェック
		if "serviceID" in self.iac_con.con_info:

			for i in range(3):
				# CCSへ接続解除リクエスト
				try:
					self.iac_con.terminate()

				except (CCSBadResponseError, ConnectionError, Timeout) as err:
					# CCSが不正レスポンス
					# メッセージを出力して無視
					msg = ("CCS Invalid Response or Http Error "
					 		"on terminating CCS connection.")
					self.logger.error(msg)
					self.logger.error(err)

				else:
					# 接続解除が成功したら、メセージをログ出力し終了
					msg = ("IaCloudApp　connection has been terminated "
								"and all data acquisition threads "
								"stopped by stop() method")
					self.logger.info(msg)
					break

			#　リトライしても繋がらない
			if i == 2:
				# treminateクエストでリトライアウトのメセージをログ出力
				msg =("CCS terminate request has been retried out. ")
				self.logger.error(msg)

	#-------------------------------------------------------
	# データを取得するための内部メソッド
	# RaspberryPiのCPU温度や内部統計情報など、Shellコマンドを実行し
	# 結果をobjectContentで返すサンプルコード。
	# サブクラスで、実際のデータ取得メソッドでオーバーライドする。
	#-------------------------------------------------------

	def _get_data(self, source:str, obj_content:dict):

		if source == "CPU_info":		# CPU情報を収集

			# データオプションを取得
			content_data = obj_content["contentData"]

			# dataContent内の各dataItemごとに
			for data_item in content_data:
				# dataItemオプション
				options = data_item.pop("options")

				# OS shellコマンドを実行し数値を取得
				cmnd = options["source"]
				args = ["bash", "-c", cmnd]
				# データのゲインとオフセットを調整
				data_value = float(
						int(subprocess.check_output(args))
						* options["gain"]
						+ options["offset"]
						)
				# loggerに、読み込んだ数値と計算値を出力（デバッグ用）
				msg = " the collected value:{}".format(data_value)
				self.logger.debug(msg)
				# dataContentのdataItemにdataValueを格納
				data_item["dataValue"] = data_value
		# 扱えないデータソースの場合
		else : obj_content["dataValue"] = None

		return obj_content

	#--------------------------------------------------------
	# 周期データ収集処理の内部メソッド、収集オブジェクト毎に個別のスレッドとして
	# IaCloudApp.start()メソッドから起動される
	#  (データを取得しデータオブジェクトを生成、CCSへ定期送信する)
	#--------------------------------------------------------
	def _acq_loop(self, obj_config:OrderedDict, event:threading.Event):

		# 収集対象オブジェクトの収集オプションを取り出す
		options = obj_config.pop("options")
		# 収集データのソースをセット
		source = options["source"]
		# データを格納する収集オブジェクトのを用意
		obj_content = obj_config.pop("ObjectContent")

		''' obj_configには、iaCloudObjectの"objectKey","objectType",
		"objectDescription","timeStamp"　のみが残ってる。	　　　　　　　'''

		while True:

			# 処理開始時刻秒を保持
			st = time.time()

			# 指定されたデータソースからデータを読み出し、CCSへストアする
			# iaCloudObjectContentにデータを格納
			# obj_contentはdeepcopyで渡す
			new_obj_c= self._get_data(source=source,
				obj_content=copy.deepcopy(obj_content)
				)

			# 取得したデータコンテントを挿入
			obj_config["ObjectContent"] = new_obj_c

			# タイムスタンプをセット
			obj_config["timeStamp"]\
				= datetime.datetime.now(self.tz).isoformat('T')

			for i in range(3):

				try:
					# CCSへデータをストアー
					self.iac_con.store(obj_config)

				except (CCSBadResponseError,
						ConnectionError,
						HTTPError, Timeout) as err:
					# ストアーリクエストでエラーが発生、CCSが不正レスポンス
					msg = "CCS Invalid Response or Http Error on periodic store."
					self.logger.error(msg)
					self.logger.error(err)
					self.logger.error(json.dumps(obj_config))

				else:
					# ストアー完了
					self.logger.info("CCS periodic store request has "
										"been sent successfully")
					self.logger.debug(json.dumps(obj_config))
					break

			if i == 2:
				# ストアーリクエストでリトライアウトのメセージをログ出力
				msg =("CCS periodic store request has been retried out. "
					"The periodic acq. thread continues without data stored.")
				self.logger.error(msg)

				'''
				# ここで、アプリケーション終了の時は、mainスレッドに通知アラーム発信し
				signal.alarm(1)
				# 停止イベントを待つ
				if event.wait():
					break
				'''
			# 周期収集処理を開始してからの処理時間を引いた時間
			wtime = options["period"] - time.time() + st

			# 次の収集タイミンングまで待つ
			# ウエイト時間が経過するとFalesが返り、再度処理開始
			# EventがセットされるとTrueが返り、スレッド終了
			if event.wait(wtime):
				break

	#--------------------------------------------------------
	# 定期的データ収集処理のスレッドを作成し起動
	#--------------------------------------------------------
	def start(self):
		'''
		To get periodic acquisition threads started.

		Usage:
			iac_app = iaCloudCApp(FDS_config)
			iac_app.start()
		'''

		# CCSへ格納すべきデータオブジェクトリストを取得
		obj_conf_list = self.options["periodicObjects"]

		# 対象オブジェクトごとにデータを取得しCCSへストアするスレッドを生成
		for obj_name in obj_conf_list :
			# データオブジェクトを用意
			obj_config = self.object_confs[obj_name]

			# 定期実行のスレッドを作成
			self.acq_th[obj_name] = threading.Thread(
				target=self._acq_loop, name=obj_name,
				args=(obj_config, self.event,)
				)
			# スレッドをスタート
			self.acq_th[obj_name].start()

	#--------------------------------------------------------
	# 非同期データ収集処理のメソッド、収集オブジェクト毎に個別のスレッドとして
	# IaCloudApp.async_trigger()メソッドから起動される。
	# データを取得しデータオブジェクトを生成、CCSへ送信する。
	#--------------------------------------------------------
	def _acq_async(self, obj_config:OrderedDict):

		# 収集対象オブジェクトの収集オプションを取り出す
		options = obj_config.pop("options")
		# 収集データのソースをセット
		source = options["source"]

		# データを格納する収集オブジェクトのを用意
		obj_content = obj_config.pop("ObjectContent")

		''' obj_configには、iaCloudObjectの"objectKey","objectType",
		"objectDescription","timeStamp"　のみが残ってる。	　　　　　　　'''

		# 指定されたデータソースからデータを読み出し、CCSへストアする
		# iaCloudObjectContentにデータを格納
		new_obj_c= self._get_data(source=source, obj_content=obj_content)

		# 取得したデータコンテントを格納
		obj_config["ObjectContent"] = new_obj_c

		# タイムスタンプをセット
		obj_config["timeStamp"]\
			= datetime.datetime.now(self.tz).isoformat('T')

		for i in range(3):
			try:
				# CCSへデータをストアー
				self.iac_con.store(obj_config)

			except (CCSBadResponseError,
					ConnectionError,
					HTTPError, Timeout) as err:
				# ストアーリクエストでエラーが発生、CCSが不正レスポンス
				msg = "CCS Invalid Response or Http Error on async store."
				self.logger.error(msg)
				self.logger.error(err)
				self.logger.error(json.dumps(obj_config))

			else:
				# ストアー完了
				self.logger.info("CCS async store request has been "
									"sent successfully")
				self.logger.debug(json.dumps(obj_config))
				break

		if i == 2:
			# ストアーリクエストでリトライアウトのメセージをログ出力
			msg =("CCS async store request has been retried out. "
					"The async acq. thread ends without data stored")
			self.logger.error(msg)

			# スレッドは終了し、次の収集トリガーを待つ
			''' ここでアプリケーション終了とする場合は、
			signal.alarm(1)
			を実行
			'''

	#-------------------------------------------------------
	# 非同期のデータ収集のスレッドを起動するメソッド。アプリケーション内で、
	# 関数でラップして使用したり、子クラス内でオーバーライドすることを想定
	#-------------------------------------------------------
	def async_trigger(self, obj_name:str):
		'''
		Async. data acqisition trigger method.
		A new thread would be dispached for async data acquisition.

		Args:
			obj_name(str):
				A name of ia-cloud data object to get and store.
				It is supposed to be in the list of
				iaCloudConfig["options"]["objects"]
		'''
		# データオブジェクトの辞書から、名前でオブジェクトを取り出し、収集を起動
		if obj_name in self.object_confs:
			self.acq_th[obj_name] = threading.Thread(
				target=self._acq_async, name=obj_name,
				args=(copy.deepcopy(self.object_confs[obj_name]),)
				)
			self.acq_th[obj_name].start()

		else:
			msg = "Target data object can't be found at async_trigger"
			self.logger.error(msg)

		# Asyncスレッドの終了を待つ。1分以上は待たない。
		self.acq_th[obj_name].join(60)

	#-------------------------------------------------------
	# ロガーを定義する内部メソッド定義
	#-------------------------------------------------------
	def _createlogger(self, name:str):

		# デバッグ・エラーのログファイルを設定
		logger = logging.getLogger(name)

		# ロガー新しく生成され、ハンドラーがまだ設定されていないなら
		if not logger.hasHandlers():

			logger.setLevel("DEBUG")

			# formatterとhandlersを作成しセットする
			formatter = logging.Formatter(
				'%(asctime)s - %(name)s - %(levelname)s - %(message)s')

			# ローテーティングファイルのハンドラーをセット
			rfh = logging.handlers.RotatingFileHandler(
				"./" + name + ".log",
				maxBytes=MAXLOGSIZE,
				backupCount=LOGROTATION,
				encoding="utf_8"
				)
			rfh.setFormatter(formatter)
			if self.debug:
				rfh.setLevel("DEBUG")
			else:
				rfh.setLevel("INFO")
			logger.addHandler(rfh)

			# 標準エラー出力にもメッセージを出す
			sh = logging.StreamHandler()
			sh.setFormatter(formatter)
			if self.debug:
				sh.setLevel("DEBUG")
			else:
				sh.setLevel("INFO")
			logger.addHandler(sh)

		return logger
