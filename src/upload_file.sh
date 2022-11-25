source .conf

export GST_PLUGIN_PATH=/home/ubuntu/lib/kinesis-video/build
export LD_LIBRARY_PATH=/home/ubuntu/lib/kinesis-video/open-source/local/lib
export AWS_DEFAULT_REGION=us-east-1

# ffmpeg -i "$1" -c:v libx264 -crf 22 -preset slow "output.mkv"

# gst-launch-1.0 -v  filesrc location="$1" ! h264parse !\
#  video/x-h264,stream-format=avc,alignment=au !\
#  kvssink name=sink stream-name="$2"\
#  access-key=$aa_id\
#  secret-key=$sk\
#  streaming-type=offline

# "filesrc location=%s ! %s ! h264parse ! video/x-h264,stream-format=avc,alignment=au ! %s",
  #            file_path.c_str(), demuxer, data->kvssink_str.c_str()

gst-launch-1.0 -v filesrc location="$1" !\
 matroskademux ! h264parse ! video/x-h264,stream-format=avc,alignment=au !\
 kvssink stream-name="$2" access-key=$aa_id secret-key=$sk streaming-type=offline

#gst-launch-1.0 -v filesrc location="$1" !\
# matroskademux name=demux ! queue ! h264parse !\
# kvssink name=sink stream-name="$2" access-key=$aa_id secret-key=$sk\
# streaming-type=offline demux. ! queue ! sink.
