#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长江雨课堂视频播放心跳机制实现
"""

import requests
import json
import time
import random
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import os
from dotenv import load_dotenv
import struct

# 加载环境变量
load_dotenv()


def getVideoDuration(url: str):
    r = requests.get(url, stream=True)
    for data in r.iter_content(chunk_size=512):
        if data.find(b'mvhd') > 0:
            index = data.find(b'mvhd') + 4
            time_scale = struct.unpack('>I', data[index + 13:index + 13 + 4])
            durations = struct.unpack('>I', data[index + 13 + 4:index + 13 + 4 + 4])
            duration = durations[0] / time_scale[0]
            return duration
            break


class YuketangHeartbeat:
    def __init__(self, cookies=None):
        self.session = requests.Session()
        self.base_url = "https://changjiang.yuketang.cn"
        self.heartbeat_url = f"{self.base_url}/video-log/heartbeat/"
        self.progress_url = f"{self.base_url}/video-log/get_video_watch_progress/"

        # 设置默认headers
        self.headers = {
            'Accept': '*/*',
            'Accept-Language': 'en,zh-CN;q=0.9,zh;q=0.8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Origin': 'https://changjiang.yuketang.cn',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'xtbz': 'ykt'
        }

        # 设置cookies
        if cookies:
            self.session.cookies.update(cookies)

        # 视频参数
        self.video_params = {}
        self.sequence = 0
        # 线程锁，确保sequence安全
        self.sequence_lock = threading.Lock()

    def create_worker_instance(self, cookies=None):
        """创建一个独立的工作实例，用于并发处理"""
        # 使用传入的cookies或复制当前实例的cookies
        if cookies is None:
            cookies = dict(self.session.cookies)

        # 创建新实例
        worker = YuketangHeartbeat(cookies)

        # 复制基本配置
        if hasattr(self, 'video_params'):
            worker.video_params = copy.deepcopy(self.video_params)

        return worker

    def set_video_params(self, user_id, course_id, video_id, sku_id, classroom_id,
                        cc_id, duration, csrf_token, university_id, uv_id):
        """设置视频播放参数"""
        self.video_params = {
            'user_id': user_id,
            'course_id': course_id,
            'video_id': video_id,
            'sku_id': sku_id,
            'classroom_id': classroom_id,
            'cc_id': cc_id,
            'duration': duration,
            'csrf_token': csrf_token,
            'university_id': university_id,
            'uv_id': uv_id
        }

        # 更新headers中的特定字段
        self.headers.update({
            'X-CSRFToken': csrf_token,
            'classroom-id': str(classroom_id),
            'university-id': str(university_id),
            'uv-id': str(uv_id),
            'Referer': f'https://changjiang.yuketang.cn/v2/web/xcloud/video-student/{classroom_id}/{video_id}'
        })

    def create_heartbeat_data(self, event_type, current_position, first_position=None,
                             true_position=None, speed=1.0):
        """创建心跳数据"""
        timestamp = str(int(time.time() * 1000))

        # 如果没有指定first_position和true_position，使用current_position
        if first_position is None:
            first_position = current_position
        if true_position is None:
            true_position = current_position

        with self.sequence_lock:
            self.sequence += 1
            current_sequence = self.sequence

        heart_data = {
            "i": 5,  # 固定值
            "et": event_type,  # 事件类型：play, playing, pause, waiting等
            "p": "web",  # 平台
            "n": "ali-cdn.xuetangx.com",  # CDN
            "lob": "ykt",  # 固定值
            "cp": current_position,  # 当前播放位置
            "fp": first_position,  # 首次播放位置
            "tp": true_position,  # 真实播放位置
            "sp": speed,  # 播放速度
            "ts": timestamp,  # 时间戳
            "u": self.video_params['user_id'],
            "uip": "",  # 用户IP（可为空）
            "c": self.video_params['course_id'],
            "v": self.video_params['video_id'],
            "skuid": self.video_params['sku_id'],
            "classroomid": str(self.video_params['classroom_id']),
            "cc": self.video_params['cc_id'],
            "d": self.video_params['duration'],
            "pg": f"{self.video_params['video_id']}_q8mn",  # 页面标识
            "sq": current_sequence,  # 序列号
            "t": "video",  # 类型
            "cards_id": 0,
            "slide": 0,
            "v_url": ""
        }

        return heart_data

    def send_heartbeat(self, heart_data_list):
        """发送心跳数据"""
        payload = {
            "heart_data": heart_data_list
        }

        try:
            response = self.session.post(
                self.heartbeat_url,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"心跳请求失败，状态码: {response.status_code}")
                return None

        except Exception as e:
            print(f"发送心跳失败: {e}")
            return None
    def get_video_progress(self):
        """获取视频播放进度"""
        params = {
            'cid': self.video_params['course_id'],
            'user_id': self.video_params['user_id'],
            'classroom_id': self.video_params['classroom_id'],
            'video_type': 'video',
            'vtype': 'rate',
            'video_id': self.video_params['video_id'],
            'snapshot': 1
        }

        progress_headers = self.headers.copy()
        progress_headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Xt-Agent': 'web'
        })

        try:
            response = self.session.get(
                self.progress_url,
                headers=progress_headers,
                params=params,
                timeout=10
            )


            if response.status_code == 200:
                # print(f"hello -{response.json()}")
                return response.json()
            else:
                print(f"获取进度失败，状态码: {response.status_code}")
                return None

        except Exception as e:
            print(f"获取进度失败: {e}")
            return None

    def get_leaf_info(self, classroom_id, leaf_id):
        """获取视频单元信息"""
        url = f"{self.base_url}/mooc-api/v1/lms/learn/leaf_info/{classroom_id}/{leaf_id}/"

        headers = self.headers.copy()
        headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Xt-Agent': 'web',
            'classroom-id': str(classroom_id)  # 添加必需的classroom-id头部
        })

        print(f"正在请求URL: {url}")

        try:
            response = self.session.get(url, headers=headers, timeout=10)

            print(f"响应状态码: {response.status_code}")

            if response.status_code == 200:
                try:
                    json_data = response.json()
                    if json_data.get('success'):
                        print("成功获取视频单元信息")
                        return json_data
                    else:
                        print(f"API返回失败: {json_data.get('msg', '未知错误')}")
                        print(f"响应内容: {response.text[:500]}...")
                        return None
                except json.JSONDecodeError:
                    print("响应不是有效的JSON格式")
                    print(f"响应内容: {response.text[:500]}...")
                    return None
            else:
                print(f"获取视频单元信息失败，状态码: {response.status_code}")
                print(f"响应内容: {response.text}")
                return None

        except Exception as e:
            print(f"获取视频单元信息失败: {e}")
            return None

    def get_video_info_alternative(self, classroom_id, leaf_id):
        """使用备用方法获取视频信息"""
        print(f"尝试备用方法获取视频信息: classroom_id={classroom_id}, leaf_id={leaf_id}")

        # 方法1: 尝试学习进度API
        url1 = f"{self.base_url}/mooc-api/v1/lms/learn/leafprogress/{classroom_id}/{leaf_id}/"
        headers = self.headers.copy()
        headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Xt-Agent': 'web',
            'classroom-id': str(classroom_id)
        })

        print(f"方法1 - 尝试学习进度API: {url1}")
        try:
            response = self.session.get(url1, headers=headers, timeout=10)
            print(f"方法1响应状态码: {response.status_code}")
            if response.status_code == 200:
                json_data = response.json()
                if json_data.get('success'):
                    print("方法1成功获取视频信息")
                    return json_data
                else:
                    print(f"方法1失败: {json_data.get('msg', '未知错误')}")
            else:
                print(f"方法1失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"方法1异常: {e}")

        # 方法2: 尝试课程内容API
        url2 = f"{self.base_url}/mooc-api/v1/lms/learn/leaf/{leaf_id}/"
        print(f"方法2 - 尝试课程内容API: {url2}")
        try:
            response = self.session.get(url2, headers=headers, timeout=10)
            print(f"方法2响应状态码: {response.status_code}")
            if response.status_code == 200:
                json_data = response.json()
                if json_data.get('success'):
                    print("方法2成功获取视频信息")
                    return json_data
                else:
                    print(f"方法2失败: {json_data.get('msg', '未知错误')}")
            else:
                print(f"方法2失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"方法2异常: {e}")

        # 方法3: 尝试不同的路径格式
        url3 = f"{self.base_url}/mooc-api/v1/lms/learn/leaf_info/{leaf_id}/"
        print(f"方法3 - 尝试简化路径: {url3}")
        try:
            response = self.session.get(url3, headers=headers, timeout=10)
            print(f"方法3响应状态码: {response.status_code}")
            if response.status_code == 200:
                json_data = response.json()
                if json_data.get('success'):
                    print("方法3成功获取视频信息")
                    return json_data
                else:
                    print(f"方法3失败: {json_data.get('msg', '未知错误')}")
            else:
                print(f"方法3失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"方法3异常: {e}")

        print("所有备用方法都失败了")
        return None

    def find_video_in_course_structure(self, classroom_id, leaf_id, sign=None):
        """在课程结构中查找指定的视频ID，获取其详细信息"""
        print(f"在课程结构中查找视频ID: {leaf_id}")

        chapters_data = self.get_course_chapters(classroom_id, sign)
        if not chapters_data or not chapters_data.get('success'):
            print("无法获取课程章节数据")
            return None

        chapters = chapters_data.get('data', {}).get('course_chapter', [])

        for chapter in chapters:
            chapter_name = chapter.get('name', '未知章节')
            section_leaf_list = chapter.get('section_leaf_list', [])

            for leaf in section_leaf_list:
                if leaf.get('id') == leaf_id:
                    print(f"找到视频: {leaf.get('name')} (ID: {leaf_id}) 在章节: {chapter_name}")
                    # 返回完整的leaf信息
                    return {
                        'success': True,
                        'data': leaf,
                        'chapter_name': chapter_name
                    }

        print(f"在课程结构中未找到视频ID: {leaf_id}")
        return None

    def debug_video_ids(self, classroom_id, sign=None, limit=5):
        """调试视频ID获取问题"""
        print(f"开始调试视频ID问题...")

        # 获取视频列表
        video_leafs = self.get_video_leaf_list(classroom_id, sign, debug=True)
        if not video_leafs:
            print("没有找到视频")
            return

        print(f"找到 {len(video_leafs)} 个视频，测试前 {limit} 个:")

        for i, video_info in enumerate(video_leafs[:limit]):
            leaf_id = video_info['id']
            print(f"\n{'='*50}")
            print(f"调试视频 {i+1}/{min(limit, len(video_leafs))}: ID={leaf_id}")
            print(f"名称: {video_info['name']}")
            print(f"章节: {video_info['chapter_name']}")
            print(f"原始leaf_type: {video_info['leaf_type']}")
            print(f"原始sku_id: {video_info['sku_id']}")

            # 测试各种获取方法
            print(f"\n1. 测试主方法 get_leaf_info:")
            leaf_info = self.get_leaf_info(classroom_id, leaf_id)
            if leaf_info and leaf_info.get('success'):
                print("✅ 主方法成功")
                data = leaf_info.get('data', {})
                print(f"   user_id: {data.get('user_id')}")
                print(f"   course_id: {data.get('course_id')}")
                print(f"   sku_id: {data.get('sku_id')}")
                content_info = data.get('content_info', {})
                media = content_info.get('media', {})
                print(f"   media keys: {list(media.keys()) if media else 'None'}")
            else:
                print("❌ 主方法失败")

                print(f"\n2. 测试备用方法:")
                alt_info = self.get_video_info_alternative(classroom_id, leaf_id)
                if alt_info and alt_info.get('success'):
                    print("✅ 备用方法成功")
                else:
                    print("❌ 备用方法也失败")

                    print(f"\n3. 测试课程结构查找:")
                    structure_info = self.find_video_in_course_structure(classroom_id, leaf_id, sign)
                    if structure_info and structure_info.get('success'):
                        print("✅ 课程结构查找成功")
                        leaf_data = structure_info.get('data', {})
                        print(f"   leaf keys: {list(leaf_data.keys()) if leaf_data else 'None'}")
                        print(f"   leaf data: {leaf_data}")
                    else:
                        print("❌ 课程结构查找也失败")

        print(f"\n{'='*50}")
        print("调试完成")

    def get_video_drag_permission(self, sku_id, classroom_id=None):
        """获取视频拖拽权限"""
        url = f"{self.base_url}/mooc-api/v1/lms/learn/video/drag"
        params = {'sku_id': sku_id}

        headers = self.headers.copy()
        headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Xt-Agent': 'web'
        })

        # 如果有classroom_id，添加到headers
        if classroom_id:
            headers['classroom-id'] = str(classroom_id)

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取拖拽权限失败，状态码: {response.status_code}")
                return None

        except Exception as e:
            print(f"获取拖拽权限失败: {e}")
            return None

    def get_watermark_config(self, uv_id, classroom_id):
        """获取水印配置"""
        url = f"{self.base_url}/c27/api/v1/platfrom/watermark"
        params = {
            'uv_id': uv_id,
            'classroom_id': classroom_id
        }

        headers = self.headers.copy()
        headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Xt-Agent': 'web',
            'classroom-id': str(classroom_id)
        })

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取水印配置失败，状态码: {response.status_code}")
                return None

        except Exception as e:
            print(f"获取水印配置失败: {e}")
            return None

    def get_video_play_url(self, video_id, provider='cc', file_type=1, is_single=0):
        """获取视频播放地址"""
        url = f"{self.base_url}/api/open/audiovideo/playurl"
        params = {
            'video_id': video_id,
            'provider': provider,
            'file_type': file_type,
            'is_single': is_single,
            'domain': 'changjiang.yuketang.cn'
        }

        headers = self.headers.copy()
        headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Xt-Agent': 'web'
        })

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取视频播放地址失败，状态码: {response.status_code}")
                return None

        except Exception as e:
            print(f"获取视频播放地址失败: {e}")
            return None

    def get_classroom_info(self, classroom_id):
        """获取课堂信息"""
        url = f"{self.base_url}/mooc-api/v1/lms/learn/classroom_info/"
        params = {'classroom_id': classroom_id}

        headers = self.headers.copy()
        headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Xt-Agent': 'web',
            'classroom-id': str(classroom_id)
        })

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取课堂信息失败，状态码: {response.status_code}")
                return None

        except Exception as e:
            print(f"获取课堂信息失败: {e}")
            return None

    def get_course_chapters(self, classroom_id, sign=None):
        """获取课程章节列表"""
        url = f"{self.base_url}/mooc-api/v1/lms/learn/course/chapter"
        params = {
            'cid': classroom_id,
            'term': 'latest',
            'uv_id': self.video_params.get('uv_id', ''),
            'classroom_id': classroom_id
        }

        # 如果有sign参数，添加到请求中
        if sign:
            params['sign'] = sign

        headers = self.headers.copy()
        headers.update({
            'Accept': 'application/json, text/plain, */*',
            'X-CSRFToken': self.video_params.get('csrf_token', ''),
            'platform-id': '3',
            'terminal-type': 'web',
            'university-id': str(self.video_params.get('university_id', '')),
            'x-client': 'web',
            'xtbz': 'ykt'
        })

        print(f"正在获取课程章节列表: {url}")

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=10)

            print(f"响应状态码: {response.status_code}")

            if response.status_code == 200:
                try:
                    json_data = response.json()
                    if json_data.get('success'):
                        print("成功获取课程章节列表")
                        # 调试：输出数据结构
                        print("数据结构调试:")
                        data = json_data.get('data', {})
                        print(f"data keys: {list(data.keys())}")
                        if 'course_chapter' in data:
                            chapters = data['course_chapter']
                            print(f"course_chapter 类型: {type(chapters)}, 长度: {len(chapters) if isinstance(chapters, list) else 'N/A'}")
                            if isinstance(chapters, list) and len(chapters) > 0:
                                first_chapter = chapters[0]
                                print(f"第一个章节的keys: {list(first_chapter.keys())}")
                                print(f"第一个章节示例: {first_chapter}")
                        return json_data
                    else:
                        print(f"API返回失败: {json_data.get('msg', '未知错误')}")
                        return None
                except json.JSONDecodeError:
                    print("响应不是有效的JSON格式")
                    return None
            else:
                print(f"获取课程章节失败，状态码: {response.status_code}")
                print(f"响应内容: {response.text[:500]}...")
                return None

        except Exception as e:
            print(f"获取课程章节失败: {e}")
            return None

    def get_video_leaf_list(self, classroom_id, sign=None, debug=False):
        """获取课程中所有视频类型的leaf列表"""
        chapters_data = self.get_course_chapters(classroom_id, sign)
        if not chapters_data or not chapters_data.get('success'):
            return []

        video_leafs = []
        chapters = chapters_data.get('data', {}).get('course_chapter', [])

        print(f"解析章节数据，共{len(chapters)}个章节")

        for chapter in chapters:
            chapter_name = chapter.get('name', '未知章节')
            print(f"处理章节: {chapter_name}")

            # 检查chapter中的section_leaf_list
            section_leaf_list = chapter.get('section_leaf_list', [])
            print(f"  章节包含 {len(section_leaf_list)} 个leafs")

            for leaf in section_leaf_list:
                if debug:
                    print(f"  调试 - Leaf: name='{leaf.get('name')}', type='{leaf.get('leaf_type')}' (type: {type(leaf.get('leaf_type'))}), id={leaf.get('id')}")

                # 检查是否为视频类型（根据name或leaf_type判断）
                leaf_name = leaf.get('name', '')
                leaf_type = leaf.get('leaf_type')  # 不设置默认值，保持原始的None

                # 根据leaf_type判断是否为视频：
                # leaf_type = None 通常是视频, 4 是讨论, 6 是测试, 5 是考试等
                # 或者name包含"Video"
                is_video = (leaf_name == 'Video' or
                           leaf_type is None or  # None 通常是视频类型
                           'video' in leaf_name.lower())

                if debug:
                    print(f"    is_video判断: {is_video} (leaf_type is None: {leaf_type is None})")

                if is_video:
                    # 检查这个视频section是否有leaf_list（实际的视频leaf）
                    leaf_list = leaf.get('leaf_list', [])

                    if leaf_list:
                        # 找到实际的视频leaf
                        for actual_leaf in leaf_list:
                            if actual_leaf.get('leaf_type') == 0:  # 只要leaf_type为0就是视频
                                video_info = {
                                    'id': actual_leaf.get('id'),  # 使用实际的leaf ID
                                    'name': leaf.get('name'),     # 使用section的名称
                                    'section_id': leaf.get('id'), # 保存section ID以备用
                                    'chapter_name': chapter_name,
                                    'leaf_type': actual_leaf.get('leaf_type'),
                                    'sku_id': leaf.get('sku_id'),
                                    'leafinfo_id': actual_leaf.get('leafinfo_id'),
                                }
                                video_leafs.append(video_info)
                                print(f"  找到视频: ID={video_info['id']} (实际leaf), 名称={video_info['name']}, 章节={chapter_name}")
                                break
                    else:
                        # 如果没有leaf_list，这可能是一个简单的视频section
                        # 我们需要通过其他方式找到实际的video leaf ID
                        # 根据调试信息，leafinfo_id可能指向实际的leaf
                        leafinfo_id = leaf.get('leafinfo_id')
                        if leafinfo_id:
                            video_info = {
                                'id': leafinfo_id,  # 尝试使用leafinfo_id
                                'name': leaf.get('name'),
                                'section_id': leaf.get('id'),
                                'chapter_name': chapter_name,
                                'leaf_type': leaf.get('leaf_type'),
                                'sku_id': leaf.get('sku_id'),
                                'leafinfo_id': leafinfo_id,
                            }
                            video_leafs.append(video_info)
                            print(f"  找到视频: ID={video_info['id']} (leafinfo_id), 名称={video_info['name']}, 章节={chapter_name}")
                        else:
                            # 最后的备用选项：使用section ID
                            video_info = {
                                'id': leaf.get('id'),
                                'name': leaf.get('name'),
                                'chapter_name': chapter_name,
                                'leaf_type': leaf.get('leaf_type'),
                                'sku_id': leaf.get('sku_id'),
                            }
                            video_leafs.append(video_info)
                            print(f"  找到视频: ID={video_info['id']} (section), 名称={video_info['name']}, 类型={video_info['leaf_type']}, 章节={chapter_name}")

        print(f"总共找到 {len(video_leafs)} 个视频")
        return video_leafs

    def simulate_video_watching(self, total_duration=None, speed=1.0, interval=5, start_position=0):
        """模拟观看视频"""
        # 如果没有指定总时长，使用配置中的视频时长
        if total_duration is None:
            total_duration = self.video_params.get('duration', 0)
            if total_duration == 0:
                print("未找到视频时长，无法模拟观看")
                return False

        current_position = start_position
        first_position = start_position

        print(f"开始模拟观看视频")
        print(f"  总时长: {total_duration}秒")
        print(f"  开始位置: {start_position}秒")
        print(f"  播放速度: {speed}x")
        print(f"  心跳间隔: {interval}秒")

        # 发送加载开始事件
        heart_data = self.create_heartbeat_data("loadstart", current_position, first_position, speed=speed)
        result = self.send_heartbeat([heart_data])
        if result:
            print(f"发送加载开始事件成功")

        # 如果从非0位置开始，发送seeking事件
        if start_position > 0:
            heart_data = self.create_heartbeat_data("seeking", current_position, first_position, speed=speed)
            result = self.send_heartbeat([heart_data])
            if result:
                print(f"发送定位事件成功 - 位置: {current_position}s")

        # 发送数据加载完成事件
        heart_data = self.create_heartbeat_data("loadeddata", current_position, first_position, speed=speed)
        result = self.send_heartbeat([heart_data])
        if result:
            print(f"发送数据加载完成事件成功")

        # 发送开始播放事件
        heart_data = self.create_heartbeat_data("play", current_position, first_position, speed=speed)
        result = self.send_heartbeat([heart_data])
        if result:
            print(f"发送开始播放事件成功")

        # 发送播放中事件
        heart_data = self.create_heartbeat_data("playing", current_position, first_position, speed=speed)
        result = self.send_heartbeat([heart_data])
        if result:
            print(f"发送播放中事件成功")

        # 模拟播放过程
        progress_check_counter = 0
        while current_position < total_duration:
            time.sleep(interval)
            current_position += interval * speed

            # 确保不超过总时长
            if current_position > total_duration:
                current_position = total_duration

            # 随机选择事件类型，大部分时间是playing
            event_types = ["playing", "playing", "playing", "waiting"]  # playing概率更高
            event_type = random.choice(event_types)

            heart_data = self.create_heartbeat_data(
                event_type,
                current_position,
                first_position,
                speed=speed
            )

            result = self.send_heartbeat([heart_data])
            if result:
                completion_rate = (current_position / total_duration) * 100
                print(f"发送心跳成功 - 位置: {current_position:.1f}s/{total_duration}s ({completion_rate:.1f}%), 事件: {event_type}")

            # 定期获取进度
            progress_check_counter += 1
            if progress_check_counter * interval >= 30:  # 每30秒获取一次进度
                progress = self.get_video_progress()
                if progress and progress.get('code') == 0:
                    video_id = str(self.video_params['video_id'])
                    progress_data = progress.get('data', {}).get(video_id, {})
                    if progress_data:
                        rate = progress_data.get('rate', 0)
                        last_point = progress_data.get('last_point', 0)
                        print(f"服务器进度: 完成率={rate:.2%}, 最后位置={last_point:.1f}s")
                progress_check_counter = 0

        # 发送视频结束事件
        heart_data = self.create_heartbeat_data("videoend", total_duration, first_position, speed=speed)
        result = self.send_heartbeat([heart_data])
        if result:
            print(f"发送视频结束事件成功")

        # 发送暂停事件
        heart_data = self.create_heartbeat_data("pause", total_duration, first_position, speed=speed)
        result = self.send_heartbeat([heart_data])
        if result:
            print(f"发送暂停事件成功")

        print("视频观看模拟完成")

        # 最终获取一次进度
        final_progress = self.get_video_progress()
        if final_progress and final_progress.get('code') == 0:
            video_id = str(self.video_params['video_id'])
            progress_data = final_progress.get('data', {}).get(video_id, {})
            if progress_data:
                rate = progress_data.get('rate', 0)
                last_point = progress_data.get('last_point', 0)
                print(f"最终进度: 完成率={rate:.2%}, 最后位置={last_point:.1f}s")

        return True

    def auto_configure_from_ids(self, classroom_id, leaf_id, sign=None):
        """根据课堂ID和视频ID自动配置参数"""
        print(f"开始自动配置参数 - 课堂ID: {classroom_id}, 视频ID: {leaf_id}")

        # 获取视频单元信息
        leaf_info = self.get_leaf_info(classroom_id, leaf_id)
        print(f"auto_configure_from_ids - {leaf_info}")
        if not leaf_info or not leaf_info.get('success'):
            print("主方法失败，尝试备用方法获取视频信息...")
            leaf_info = self.get_video_info_alternative(classroom_id, leaf_id)
            if not leaf_info or not leaf_info.get('success'):
                print("API方法都失败，尝试从课程结构中获取信息...")
                structure_info = self.find_video_in_course_structure(classroom_id, leaf_id, sign)
                if structure_info and structure_info.get('success'):
                    # 使用课程结构中的信息
                    leaf_data = structure_info.get('data', {})
                    print(f"从课程结构获取信息成功，视频名称: {leaf_data.get('name', '未知')}")

                    # 尝试使用课程结构中的sku_id等信息
                    sku_id = leaf_data.get('sku_id')
                    if sku_id:
                        print(f"使用课程结构中的sku_id: {sku_id}")
                        # 模拟一个简单的leaf_info结构
                        leaf_info = {
                            'success': True,
                            'data': {
                                'sku_id': sku_id,
                                'name': leaf_data.get('name', '未知视频'),
                                'content_info': {
                                    'media': {
                                        'duration': leaf_data.get('duration', 0),
                                        'ccid': leaf_data.get('video_id'),  # 可能存在
                                        'cc_id': leaf_data.get('video_id'),
                                        'cc': leaf_data.get('video_id')
                                    }
                                }
                            }
                        }
                    else:
                        print("课程结构中也没有足够的信息")
                        return False
                else:
                    print("所有方法都失败，无法获取视频单元信息")
                    return False

        data = leaf_info.get('data', {})
        content_info = data.get('content_info', {})
        media = content_info.get('media', {})

        # 打印数据结构以便调试
        print("数据结构调试:")
        print(f"data keys: {list(data.keys()) if data else 'None'}")
        print(f"content_info keys: {list(content_info.keys()) if content_info else 'None'}")
        print(f"media keys: {list(media.keys()) if media else 'None'}")
        print(f"media内容: {media}")

        # 提取关键参数
        user_id = data.get('user_id')
        course_id = data.get('course_id')
        sku_id = data.get('sku_id')
        university_id = data.get('university_id')

        # 从媒体信息中提取cc_id，尝试多种可能的字段名
        cc_id = media.get('ccid') or media.get('cc_id') or media.get('cc') or media.get('video_id')
        #

        #bug: 此处获取不到duration

        # 获取课堂信息
        classroom_info = self.get_classroom_info(classroom_id)
        if classroom_info and classroom_info.get('success'):
            classroom_data = classroom_info.get('data', {})
            # 可以从课堂信息中获取更多参数

        # 获取拖拽权限
        if sku_id:
            drag_info = self.get_video_drag_permission(sku_id, classroom_id)
            if drag_info and drag_info.get('success'):
                has_drag = drag_info.get('data', {}).get('has_drag', False)
                print(f"拖拽权限: {'允许' if has_drag else '禁止'}")

        # 获取水印配置
        if university_id:
            watermark_config = self.get_watermark_config(university_id, classroom_id)
            if watermark_config and watermark_config.get('success'):
                watermark_data = watermark_config.get('data', {})
                print(f"水印配置: {watermark_data}")

        # 获取视频播放地址
        if cc_id:
            play_url_info = self.get_video_play_url(cc_id)
            if play_url_info and play_url_info.get('success'):
                sources = play_url_info.get('data', {}).get('playurl', {}).get('sources', {})
                play_urls = []
                for quality, urls in sources.items():
                    # print(quality)
                    play_urls.extend(urls)
                print(f"视频播放地址获取成功，共{len(play_urls)}个清晰度")
                # print(play_urls)
        duration = getVideoDuration(play_urls[0])

        # 检查必要参数
        if not all([user_id, course_id, sku_id, cc_id]):
            print("缺少必要参数:")
            print(f"  user_id: {user_id}")
            print(f"  course_id: {course_id}")
            print(f"  sku_id: {sku_id}")
            print(f"  cc_id: {cc_id}")
            return False

        # 从cookies中获取csrf_token
        csrf_token = None
        for cookie in self.session.cookies:
            if cookie.name == 'csrftoken':
                csrf_token = cookie.value
                break

        if not csrf_token:
            print("未找到CSRF token")
            return False

        # 自动设置视频参数
        self.set_video_params(
            user_id=user_id,
            course_id=course_id,
            video_id=leaf_id,
            sku_id=sku_id,
            classroom_id=classroom_id,
            cc_id=cc_id,
            csrf_token=csrf_token,
            university_id=university_id,
            uv_id=university_id,
            duration=duration,
        )

        print("参数配置完成:")
        print(f"  视频名称: {data.get('name', '未知')}")
        print(f"  用户ID: {user_id}")
        print(f"  课程ID: {course_id}")
        print(f"  视频ID: {leaf_id}")
        print(f"  SKU ID: {sku_id}")
        print(f"  课堂ID: {classroom_id}")
        print(f"  CC ID: {cc_id}")
        print(f"  视频时长: {duration}秒")
        print(f"  学校ID: {university_id}")

        return True

    def get_current_progress_info(self):
        """获取当前播放进度信息"""
        progress = self.get_video_progress()
        if progress and progress.get('code') == 0:
            video_id = str(self.video_params['video_id'])
            progress_data = progress.get('data', {}).get(video_id, {})
            if progress_data:
                return {
                    'rate': progress_data.get('rate', 0),
                    'last_point': progress_data.get('last_point', 0),
                    'duration': self.video_params.get('duration', 0)
                }
        return None

    def smart_watch_video(self, speed=1.5, interval=5):
        """智能观看视频（从上次停止的位置开始）"""
        # 获取当前进度
        progress_info = self.get_current_progress_info()
        if not progress_info:
            print("无法获取进度信息，从头开始播放")
            start_position = 0
        else:
            rate = progress_info['rate']
            last_point = progress_info['last_point']
            duration = progress_info['duration']

            print(f"当前进度: {rate:.2%}, 最后位置: {last_point:.1f}s, 总时长: {duration}")

            if rate >= 0.9:  # 如果已经看了90%以上
                print("视频已基本看完，无需继续观看")
                return True

            # 从最后位置开始播放
            start_position = max(0, last_point - 10)  # 往前退10秒，避免遗漏

        # 开始模拟观看
        return self.simulate_video_watching(
            speed=speed,
            interval=interval,
            start_position=start_position
        )

    def watch_single_video_worker(self, video_info, classroom_id, sign, speed, interval, skip_completed, worker_id):
        """单个视频观看的工作函数，用于并发执行"""
        leaf_id = video_info['id']
        video_name = video_info['name']
        chapter_name = video_info['chapter_name']

        print(f"[Worker-{worker_id}] 开始处理视频: {video_name} (ID: {leaf_id})")

        try:
            # 创建独立的工作实例
            worker = self.create_worker_instance()

            # 自动配置视频参数
            if not worker.auto_configure_from_ids(classroom_id, leaf_id, sign):
                print(f"[Worker-{worker_id}] ❌ 配置视频参数失败: {video_name}")
                return {'status': 'failed', 'video_info': video_info, 'reason': '参数配置失败'}

            # 检查是否已完成
            if skip_completed:
                progress_info = worker.get_current_progress_info()
                if progress_info and progress_info['rate'] >= 0.9:
                    print(f"[Worker-{worker_id}] ✅ 视频已完成 ({progress_info['rate']:.1%}): {video_name}")
                    return {'status': 'skipped', 'video_info': video_info, 'rate': progress_info['rate']}

            # 开始观看视频
            print(f"[Worker-{worker_id}] 🎬 开始观看视频: {video_name}")
            if worker.smart_watch_video(speed=speed, interval=interval):
                print(f"[Worker-{worker_id}] ✅ 视频观看完成: {video_name}")
                return {'status': 'success', 'video_info': video_info}
            else:
                print(f"[Worker-{worker_id}] ❌ 视频观看失败: {video_name}")
                return {'status': 'failed', 'video_info': video_info, 'reason': '观看失败'}

        except Exception as e:
            print(f"[Worker-{worker_id}] ❌ 处理视频时发生异常: {video_name}, 错误: {str(e)}")
            return {'status': 'failed', 'video_info': video_info, 'reason': f'异常: {str(e)}'}

    def concurrent_watch_videos(self, classroom_id, sign=None, speed=1.5, interval=5, skip_completed=True, max_workers=3, test_mode=False, test_video_count=5):
        """并发观看课程中的所有视频"""
        print(f"开始并发观看视频... (最大并发数: {max_workers})")

        # 获取所有视频列表
        video_leafs = self.get_video_leaf_list(classroom_id, sign)

        if not video_leafs:
            print("没有找到任何视频")
            return

        # 测试模式：只处理前几个视频
        if test_mode:
            video_leafs = video_leafs[:test_video_count]
            print(f"🧪 测试模式：只处理前 {len(video_leafs)} 个视频")
        else:
            print(f"准备观看 {len(video_leafs)} 个视频")

        success_count = 0
        skip_count = 0
        failed_count = 0

        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_video = {
                executor.submit(
                    self.watch_single_video_worker,
                    video_info,
                    classroom_id,
                    sign,
                    speed,
                    interval,
                    skip_completed,
                    i + 1
                ): video_info
                for i, video_info in enumerate(video_leafs)
            }

            # 收集结果
            completed_count = 0
            for future in as_completed(future_to_video):
                completed_count += 1
                video_info = future_to_video[future]

                try:
                    result = future.result()
                    status = result['status']
                    video_name = result['video_info']['name']

                    if status == 'success':
                        success_count += 1
                        print(f"[主线程] ✅ ({completed_count}/{len(video_leafs)}) 成功完成: {video_name}")
                    elif status == 'skipped':
                        skip_count += 1
                        rate = result.get('rate', 0)
                        print(f"[主线程] ⏭️ ({completed_count}/{len(video_leafs)}) 跳过已完成 ({rate:.1%}): {video_name}")
                    else:
                        failed_count += 1
                        reason = result.get('reason', '未知原因')
                        print(f"[主线程] ❌ ({completed_count}/{len(video_leafs)}) 失败 ({reason}): {video_name}")

                except Exception as e:
                    failed_count += 1
                    print(f"[主线程] ❌ ({completed_count}/{len(video_leafs)}) 处理结果时发生异常: {str(e)}")

                # 添加短暂延迟，避免请求过快
                time.sleep(0.5)

        print(f"\n{'='*60}")
        print("并发观看完成！")
        print(f"总视频数: {len(video_leafs)}")
        print(f"成功观看: {success_count}")
        print(f"跳过（已完成）: {skip_count}")
        print(f"失败: {failed_count}")
        print(f"{'='*60}")

        return {
            'total': len(video_leafs),
            'success': success_count,
            'skipped': skip_count,
            'failed': failed_count
        }

    def batch_watch_videos(self, classroom_id, sign=None, speed=1.5, interval=5, skip_completed=True):
        """批量观看课程中的所有视频"""
        print("开始批量观看视频...")

        # 获取所有视频列表
        video_leafs = self.get_video_leaf_list(classroom_id, sign)

        if not video_leafs:
            print("没有找到任何视频")
            return

        print(f"准备观看 {len(video_leafs)} 个视频")

        success_count = 0
        skip_count = 0
        failed_count = 0

        for i, video_info in enumerate(video_leafs, 1):
            leaf_id = video_info['id']
            chapter_name = video_info['chapter_name']

            print(f"\n{'='*60}")
            print(f"正在处理第 {i}/{len(video_leafs)} 个视频")
            print(f"视频ID: {leaf_id}")
            print(f"章节: {chapter_name}")
            print(f"{'='*60}")

            # 自动配置视频参数
            if not self.auto_configure_from_ids(classroom_id, leaf_id, sign):
                print(f"❌ 配置视频参数失败，跳过视频 {leaf_id}")
                failed_count += 1
                continue

            # 检查是否已完成
            if skip_completed:
                progress_info = self.get_current_progress_info()
                if progress_info and progress_info['rate'] >= 0.9:
                    print(f"✅ 视频已完成 ({progress_info['rate']:.1%})，跳过")
                    skip_count += 1
                    continue

            # 开始观看视频
            print(f"🎬 开始观看视频...")
            if self.smart_watch_video(speed=speed, interval=interval):
                print(f"✅ 视频观看完成")
                success_count += 1
            else:
                print(f"❌ 视频观看失败")
                failed_count += 1

            # 添加短暂延迟，避免请求过快
            time.sleep(2)

        print(f"\n{'='*60}")
        print("批量观看完成！")
        print(f"总视频数: {len(video_leafs)}")
        print(f"成功观看: {success_count}")
        print(f"跳过（已完成）: {skip_count}")
        print(f"失败: {failed_count}")
        print(f"{'='*60}")

        return {
            'total': len(video_leafs),
            'success': success_count,
            'skipped': skip_count,
            'failed': failed_count
        }


def main():
    """主函数，演示如何使用心跳机制"""

    # 从环境变量加载配置
    classroom_id = int(os.getenv('CLASSROOM_ID', 12345678))
    sign = os.getenv('SIGN', 'your_sign_here')
    university_id = int(os.getenv('UNIVERSITY_ID', 1234))
    csrf_token = os.getenv('CSRF_TOKEN', 'your_csrf_token_here')
    session_id = os.getenv('SESSION_ID', 'your_session_id_here')

    # 视频观看配置
    video_speed = float(os.getenv('VIDEO_SPEED', 1.5))
    heartbeat_interval = int(os.getenv('HEARTBEAT_INTERVAL', 5))
    max_concurrent_videos = int(os.getenv('MAX_CONCURRENT_VIDEOS', 3))
    skip_completed = os.getenv('SKIP_COMPLETED', 'true').lower() == 'true'
    test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'
    test_video_count = int(os.getenv('TEST_VIDEO_COUNT', 5))
    use_concurrent = os.getenv('USE_CONCURRENT', 'true').lower() == 'true'
    debug = os.getenv('DEBUG', 'false').lower() == 'true'

    # 设置cookies（从环境变量获取）
    cookies = {
        'login_type': 'WX',
        'csrftoken': csrf_token,
        'sessionid': session_id,
        'django_language': 'zh-cn',
        'uv_id': str(university_id),
        'university_id': str(university_id),
        'platform_id': '3',
        'classroomId': str(classroom_id),
        'classroom_id': str(classroom_id),
        'xtbz': 'ykt',
        'platform_type': '1'
    }

    # 创建心跳对象
    heartbeat = YuketangHeartbeat(cookies)

    # 首先测试获取视频列表
    print("正在获取视频列表...")
    # 需要先配置基本参数才能调用API
    heartbeat.video_params = {
        'uv_id': university_id,
        'university_id': university_id,
        'csrf_token': csrf_token
    }

    video_list = heartbeat.get_video_leaf_list(classroom_id, sign, debug=debug)
    if video_list:
        print(f"找到 {len(video_list)} 个视频")
        for i, video in enumerate(video_list, 1):
            print(f"{i}. ID: {video['id']}, 名称: {video['name']}, 章节: {video['chapter_name']}")

        print(f"配置参数: 并发={use_concurrent}, 并发数={max_concurrent_videos}, 速度={video_speed}x, 间隔={heartbeat_interval}s")
        print(f"测试模式: {test_mode}, 跳过已完成: {skip_completed}")

        if use_concurrent:
            print(f"\n开始并发观看视频... (并发数: {max_concurrent_videos})")
            heartbeat.concurrent_watch_videos(
                classroom_id=classroom_id,
                sign=sign,
                speed=video_speed,
                interval=heartbeat_interval,
                skip_completed=skip_completed,
                max_workers=max_concurrent_videos,  # 最大并发数
                test_mode=test_mode,          # 测试模式
                test_video_count=test_video_count   # 测试视频数量
            )
        else:
            print("\n开始串行观看所有视频...")
            heartbeat.batch_watch_videos(
                classroom_id=classroom_id,
                sign=sign,
                speed=video_speed,
                interval=heartbeat_interval,
                skip_completed=skip_completed
            )
    else:
        print("未找到视频，请检查参数")



if __name__ == "__main__":
    main()