from data_generator.data import EvalData
from model.graph import Graph
from model.train import get_feed, get_session_config
from util.checkpoint import copy_ckpt_to_modeldir

import tensorflow as tf
import numpy as np

import time
from datetime import datetime
from os.path import exists
from os import makedirs

from model.model_config import get_args


args = get_args()


def eval(model_config, ckpt):
    assert model_config.num_gpus == 1 # Eval only uses single GPU

    data = EvalData(model_config)
    graph = Graph(False, model_config, data)
    tf.reset_default_graph()
    graph.create_model_multigpu()
    sess = tf.train.MonitoredTrainingSession(
        checkpoint_dir=model_config.logdir,
        config=get_session_config()
    )
    graph.saver.restore(sess, ckpt)

    perplexitys = []
    total_cnt = 0.0
    correct_cnt, correct_cnt2, correct_cnt3, correct_cnt4, correct_cnt5 = 0.0, 0.0, 0.0, 0.0, 0.0
    report = []
    line_id = 1
    start_time = datetime.now()

    while True:
        input_feed, exclude_cnt, gt_targets = get_feed(graph.objs, data, model_config, False)
        fetches = [graph.objs[0]['preds'], graph.loss, graph.global_step,
                   graph.perplexity]
        preds, loss, step, perplexity = sess.run(fetches, input_feed)
        perplexitys.append(perplexity)

        for batch_id in range(model_config.batch_size - exclude_cnt):
            gt_target = gt_targets[batch_id]
            pred = preds[batch_id]

            report.append('%s:' % str(line_id))
            line_id += 1

            for i in range(model_config.max_abbrs):
                if gt_target[i][2] == 0:
                   continue

                if gt_target[i][-1] == pred[i][0:1] :
                    correct_cnt += 1
                if gt_target[i][-1] in pred[i][0:2]:
                    correct_cnt2 += 1
                if gt_target[i][-1] in pred[i][0:3]:
                    correct_cnt3 += 1
                if gt_target[i][-1] in pred[i][0:4]:
                    correct_cnt4 += 1
                if gt_target[i][-1] in pred[i][0:5]:
                    correct_cnt5 += 1
                total_cnt += 1

                abbr_id = gt_target[i][1]

                report.append('Abbr:%s\tPred:%s\tGt:%s\t' %
                              (data.id2abbr[abbr_id],
                               ';'.join([data.id2sense[loop] for loop in pred[i]]),
                               data.id2sense[gt_target[i][-1]]))
            report.append('')

        if exclude_cnt > 0:
            break

    end_time = datetime.now()
    fmt = "%.5f"
    acc = fmt % (correct_cnt / total_cnt)
    acc2 = fmt % (correct_cnt2 / total_cnt)
    acc3 = fmt % (correct_cnt3 / total_cnt)
    acc4 = fmt % (correct_cnt4 / total_cnt)
    acc5 = fmt % (correct_cnt5 / total_cnt)
    perplexity = np.mean(perplexity)
    report = '\n'.join(report)
    filename = 'step%s_acc%s_acc2%s_acc3%s_acc4%s_acc5%s_pp%s.txt' % (step, acc, acc2, acc3, acc4, acc5, perplexity)
    span = end_time - start_time

    if not exists(model_config.resultdir):
        makedirs(model_config.resultdir)
    f = open(model_config.resultdir + filename, 'w')
    f.write(report)
    f.close()
    print('Eval Finished using %s.' % str(span))


if __name__ == '__main__':
    def get_ckpt(modeldir, logdir, wait_second=60):
        while True:
            try:
                ckpt = copy_ckpt_to_modeldir(modeldir, logdir)
                return ckpt
            except FileNotFoundError as exp:
                if wait_second:
                    print(str(exp) + '\nWait for 1 minutes.')
                    time.sleep(wait_second)
                else:
                    return None

    from model.model_config import DummyConfig, BaseConfig
    if args.mode == 'dummy':
        model_config = DummyConfig()
        while True:
            ckpt = get_ckpt(model_config.modeldir, model_config.logdir)
            if ckpt:
                eval(model_config, ckpt)
    elif args.mode == 'base':
        model_config = BaseConfig()
        while True:
            ckpt = get_ckpt(model_config.modeldir, model_config.logdir)
            if ckpt:
                eval(model_config, ckpt)
