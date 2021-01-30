#! /bin/bash

set +x 


if [[ $# -lt 3 ]] 
then 
    echo "Wrong Params"
    exit
fi

ip=$1
src_folder=$2
dest_folder=$3

scp $ip:$src_folder/*.txt $dest_folder/
scp $ip:$src_folder/*.csv $dest_folder/
scp $ip:$src_folder/*tcpdump* $dest_folder/

ls -ltr $dest_folder


