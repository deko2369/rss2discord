import os
import itertools
from collections import defaultdict
from datetime import datetime, timedelta

import discord
import asyncio
import feedparser
import pytz
import yaml


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # create the background task and run it in the background
        self.bg_task = self.loop.create_task(self.bg_task())

        self.duration = 180
        self.sites = {}
        self._load_sites()

        self._target_channels = defaultdict(list)

    def _load_sites(self):
        with open('sites.yml') as f:
            self.sites = yaml.safe_load(f)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def fetch_rss_contents(self, url, threshold_date):
        feed = await self.loop.run_in_executor(None, feedparser.parse, url)

        def parse_date(t):
            return datetime(*t[:6], tzinfo=pytz.utc)

        site_name = feed['feed']['title']
        return [discord.Embed(type='rich',
                              title=e.title,
                              url=e.link,
                              description=e.summary).set_author(name=site_name)
                for e in feed['entries'] if parse_date(e.published_parsed) > threshold_date]

    async def _init(self):
        for guild in self.guilds:
            for channel_name in self.sites.keys():
                c = None
                for text_channel in guild.text_channels:
                    if channel_name == text_channel.name:
                        c = text_channel
                        break

                if not c:
                    c = await guild.create_text_channel(channel_name)

                self._target_channels[channel_name].append(c)

    async def bg_task(self):
        try:
            await self.wait_until_ready()
            await self._init()

            while not self.is_closed():
                threshold_date = datetime.now(pytz.utc) - timedelta(seconds=self.duration)

                for channel_name, urls in self.sites.items():
                    for c in self._target_channels[channel_name]:
                        embeds = list(itertools.chain.from_iterable(
                            await asyncio.gather(*[self.fetch_rss_contents(url, threshold_date)
                                                   for url in urls])
                        ))
                        for embed in embeds:
                            await c.send(embed=embed)

                await asyncio.sleep(self.duration)
        except Exception as e:
            print(e)


client = MyClient()
client.run(os.getenv('TOKEN'))
