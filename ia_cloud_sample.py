#!/usr/bin/env python3
# -*- coding:utf-8 -*-
'''
ia-cloud sample application for raspberryPi module using a ia_cloud pakage.

Usage:
	This application gets RaspberryPi's CPU information and stores to CCS.
	Data acquisition application configration file must be provided as an
	argument of this application.
'''
import sys
import time
#jsonのパッケージ
import json
# Python組込のデータコンテナに変わるコンテナのパッケージ OrderedDictを利用
from collections import OrderedDict
# マルチスレッドのモジュール
import threading
# シグナルをハンドルするパッケージ
import signal
import logging

# ia-cloudのパッケージをインポート
from ia_cloud.ia_cloud_app import IaCloudApp

#-------------------------------------------------------
# signalイベントハンドラ
#-------------------------------------------------------
def _signal_handler(signum, frame, app:IaCloudApp):
	'''
	A signal handler function that should be set by signal.signal().
	The handler would call ia_clod_app.stop() to terminate data acquisition
	threads, set Event to stop a toggling thread and shutdown the logging
	 system. Then exit the application with sys.exit().

	Usage:
		signal.signal(signal.SIGTERM,
			(lambda a,b: _signal_handler(a, b, iac_app)))
		signal.signal(signal.SIGINT,
			(lambda a,b: _signal_handler(a, b, iac_app)))
		signal.signal(signal.SIGALRM,
			(lambda a,b: _signal_handler(a, b, iac_app)))
	Args:
		ia_clod_app(IaCloudApp): ia-cloud application instance.
	'''
	# CCSへのデータ送信を停止
	app.stop()

	if signum == signal.SIGALRM:
		# 内部エラーによるsignalの場合
		msg = "Application has been terminated by comunication error with CCS"
	else:
		# キーボードなどの割り込みによる中断
		msg = "Application has been terminated by key interruppt"
	app.logger.error(msg)

	# ロギングシステムを終了
	logging.shutdown()

	# アプリケーションを終了
	sys.exit()


#-------------------------------------------------------
# main処理スクリプト
#-------------------------------------------------------

if __name__ == "__main__":

	# 各種設定情報をここで読み取る。
	argvs = sys.argv  # コマンドライン引数を格納したリストの取得
	argc = len(argvs) # 引数の個数

	# ファイル名が引数にない場合は、デフォルトのファイル名
	fname = "./ia_cloud_config.json"  if argc == 1 else argvs[1]

	# 設定情報の入ったjsonファイルを辞書型のconfに読み込み
	with open(fname, encoding="utf-8") as f:

	# 設定ファイルからJSONを読み出す。
	# collections.OrderedDictオブジェクトを使い、json内の出現順を維持
		FDS_config = json.load(f, object_pairs_hook=OrderedDict)

	# iaCloudアプリケーションクラスをのインスタンスを作成
	iac_app = IaCloudApp(FDS_config=FDS_config)

	# エラー時やKey割り込み時のシグナルハンドラーを設定
	signal.signal(signal.SIGTERM,
		(lambda a,b: _signal_handler(a, b, iac_app)))
	signal.signal(signal.SIGINT,
		(lambda a,b: _signal_handler(a, b, iac_app)))
	signal.signal(signal.SIGALRM,
		(lambda a,b: _signal_handler(a, b, iac_app)))

	try:
		# データの周期収集をスタート
		iac_app.start()

		# 無限ループ。KeyInterruptかエラーで抜ける。
		while True:
				time.sleep(1)

	except Exception as err:

		# 予期せぬエラーが発生した場合
		msg = "IaCloudApp has been stopped by an uncaught Error"
		iac_app.logger.error(msg)
		iac_app.logger.error(err)
		iac_app.logger.error(type(err))

		# エラー終了
		sys.exit()
