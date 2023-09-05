#########################################
# TODO LIST
#
#   ・Bot書き込み用Ch名を変更できるようにする?
#   ・クラス化して整理したい。
#   ・うさぎの来る時間を調べる
#   ・imgのリンクが貼られたときの動作を修正する。
#   ・うさぎさんタスクのSeqを辞書化
#   ・sqlの要素名を辞書化
#   ・次にウサギが来る時間が24時間を超える場合の処理
#   ・ウサギさん来る時間のリスト化
#   ・ウサギさんタイマー表示用チャンネル別に分ける?
#

from myLib.L2_SystemIO.sql import SQL
import myLib.L2_SystemIO.discordIO as d_IO

#########################################
DEBUG_MODE = "Earnest_dev"
# DEBUG_MODE = "Rose_dev"
# DEBUG_MODE = "Deploy"

# DBの初期接続
SQL.init()
# クライアントの接続
d_IO.activate_client(DEBUG_MODE=DEBUG_MODE)
