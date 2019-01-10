#!/usr/bin/env bash

wpath=$HOME/data/local-jobs/mix-getter
datadir=$wpath/mixes
dldir=$datadir/dls
dimg="dijksterhuis/youtube-dl-audio:mixes"

docker build --no-cache -t $dimg $wpath

cp $HOME/Desktop/sites/mixes.txt $datadir/urls.txt
docker run -it --rm \
	-v $datadir/:/home/to-get-list/ \
	-v $dldir:/home/gotten/ \
	$dimg \
	/bin/ash -c "python /home/get_audio.py"
