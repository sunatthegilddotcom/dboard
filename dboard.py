import os
from dd_client import DD
from elasticsearch import Elasticsearch
from time import sleep
from datetime import datetime

#Parse config file and get parameters and connection settings
config_file = open('dboard.conf','r')

config_dict = {}

for line in config_file:
    if line and line[0].isalpha():
        parameter = line.split(':')[0].strip()
        value = line.split(':')[1].strip().split(';')
        config_dict[parameter] = value

dede_server = config_dict.get('dede_server')[0]
es_server = config_dict.get('es_server')[0]


#Services Parameters
solver_type_list = config_dict.get('solver_type_list')
layers_list = [layer.split(',') for layer in config_dict.get('layers_list')]
iterations_list = config_dict.get('iterations_list')
base_lr_list = config_dict.get('base_lr_list')
template_list = config_dict.get('template_list')
activation_list = config_dict.get('activation_list')
test_split_list = config_dict.get('test_split_list')
min_count_list = config_dict.get('min_count_list')
min_word_length_list = config_dict.get('min_word_length_list')
batch_size_list = config_dict.get('batch_size_list')
test_interval_list = config_dict.get('test_interval_list')
nclasses = int(config_dict.get('nclasses')[0])
root_repository = config_dict.get('root_repository')[0]
dataset_version = config_dict.get('dataset_version')[0]
dataset_description = config_dict.get('dataset_description')[0]

#Initialize the services list
services_list = []

#Set elasticsearch connection
es = Elasticsearch(es_server,request_timeout=60)

#Create log file
log_file = open("dede_testing.log","w")

#Create services names and dictionary containing the parameters

for solver in solver_type_list:
    for layers in layers_list:
        for iterations in iterations_list:
            for base_lr in base_lr_list:
                for template in template_list:
                    for activation in activation_list:
                        for test_split in test_split_list:
                            for min_count in min_count_list:
                                for min_word_length in min_word_length_list:
                                    for batch_size in batch_size_list:
                                        for test_interval in test_interval_list:
                                            service_dict = {}
                                            if template == 'mlp':
                                                service_dict["service_name"] = solver+"_"+str("-".join(str(x) for x in layers))+"_"+str(dataset_version)+"_"+str(base_lr).replace('.','-')+"_"+str(template)+"_"+str(activation)+"_"+str(min_count)+"_"+str(min_word_length)+"_"+str(batch_size)+"_"+str(test_interval)
                                                service_dict["description"] = solver+" "+str("-".join(str(x) for x in layers))+" "+str(dataset_description)+" "+str(base_lr)+" "+str(template)+" "+str(activation)+" "+str(min_count)+" "+str(min_word_length)+" "+str(batch_size)+" "+str(test_interval)
                                                service_dict["layers"] = layers
                                            else:
                                                service_dict["service_name"] = solver+"_"+str(dataset_version)+"_"+str(base_lr).replace('.','-')+"_"+str(template)+"_"+str(activation)+"_"+str(min_count)+"_"+str(min_word_length)+"_"+str(batch_size)+"_"+str(test_interval)
                                                service_dict["description"] = solver+" "+str(dataset_description)+" "+str(base_lr)+" "+str(template)+" "+str(activation)+" "+str(min_count)+" "+str(min_word_length)+" "+str(batch_size)+" "+str(test_interval)
                                            service_dict["solver_type"] = solver
                                            service_dict["iterations"] = iterations
                                            service_dict["base_lr"] = base_lr
                                            service_dict["template"] = template
                                            service_dict["activation"] = activation
                                            service_dict["test_split"] = test_split
                                            service_dict["min_count"] = min_count
                                            service_dict["min_word_length"] = min_word_length
                                            service_dict["batch_size"] = batch_size
                                            service_dict["test_interval"] = test_interval
                                            services_list.append(service_dict)


#Create folders for all models
for service in services_list:
    directory = root_repository+service['service_name']
    if not os.path.exists(directory):
        os.makedirs(directory)

#Connect to DD
dd = DD(dede_server)
dd.set_return_format(dd.RETURN_PYTHON)

#Start the creation and training of services, pulling data every 10sec
service_count = 1
for service in services_list:
    #Get start time value to avoid duplicate runs of the same service to overlap
    start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file.write("service number "+str(service_count)+" of "+str(len(services_list))+"\n")
    log_file.flush()
    service_count += 1
    #create the service
    service_name = service['service_name']
    log_file.write("Starting test for "+service_name+"\n")
    log_file.flush()
    if service['template'] == 'mlp':
        layers = [int(x) for x in service['layers']]
    description = service['description']
    template = service['template']
    activation = service['activation']
    test_split = float(service["test_split"])
    min_count = int(service["min_count"])
    min_word_length = int(service["min_word_length"])
    batch_size = int(service["batch_size"])
    test_interval = int(service["test_interval"])
    mllib = 'caffe'
    model = {'templates':'/var/deepdetect/templates/caffe/','repository':root_repository+service_name}
    parameters_input_service = {'connector':'txt'}
    if template == "mlp":
        parameters_mllib_service  = {'template':template,'nclasses':nclasses,'layers':layers,'activation':activation}
    elif template == "lregression":
        parameters_mllib_service  = {'template':template,'nclasses':nclasses,'activation':activation}
    parameters_output_service  = {'measure':['mcll','f1']}
    dd.put_service(service_name,model,description,mllib,parameters_input_service,parameters_mllib_service,parameters_output_service)
    #Start training the service
    iterations = int(service['iterations'])
    solver_type = service['solver_type']
    base_lr = float(service['base_lr'])
    parameters_input_training = {'shuffle':True,'test_split':test_split,'min_count':min_count,'min_word_length':min_word_length,'count':False}
    parameters_mllib_training = {'gpu':True,'solver':{'iterations':iterations,'test_interval':test_interval,'base_lr':base_lr,'solver_type':solver_type},'net':{'batch_size':batch_size}}
    parameters_output_training = {'measure':['mcll','f1','cmdiag','cmfull']}
    train_data = [root_repository+'dataset/']
    training_service = dd.post_train(service_name.lower(),train_data,parameters_input_training,parameters_mllib_training,parameters_output_training,async=True)
    job_number = training_service['head']['job']
    #Get training data while the service is running
    sleep(20)
    status_code = 200
    count_job_data = 1
    while status_code == 200:
        job_data = dd.get_train(service_name.lower(),job=job_number, measure_hist=True)
        status_code = job_data['status']['code']
        if not 'accp' in job_data['body']['measure']:
            sleep(20)
            continue
        if job_data['head']['status'] == 'running':
            log_file.write("job running time "+str(job_data['head']['time'])+"\n")
            log_file.write("Iteration number "+str(job_data['body']['measure']['iteration'])+"\n")
            log_file.flush()
            running_time = job_data['head']['time']
            accp = job_data['body']['measure']['accp']
            recall = job_data['body']['measure']['recall']
            iteration = job_data['body']['measure']['iteration']
            precision = job_data['body']['measure']['precision']
            mcll = job_data['body']['measure']['mcll']
            f1 = job_data['body']['measure']['f1']
            train_loss = job_data['body']['measure']['train_loss']
            doc = {
                'running_time': running_time,
                'accp': accp,
                'recall': recall,
                'iteration': iteration,
                'precision': precision,
                'service_name': service_name,
                'layers': layers,
                'description': description,
                'total_iterations': iterations,
                'solver_type': solver_type,
                'base_lr': base_lr,
                'activation': activation,
                'template': template,
                'test_split': test_split,
                'min_count': min_count,
                'min_word_length': min_word_length,
                'batch_size': batch_size,
                'start_time': start_time,
                'test_interval': test_interval,
                'dataset_version': dataset_version,
                'dataset_description': dataset_description
            }
            if not str(job_data['body']['measure']['mcll']) == 'inf':
                doc['mcll'] = job_data['body']['measure']['mcll']
            if not str(job_data['body']['measure']['train_loss']) == 'inf':
                doc['train_loss'] = job_data['body']['measure']['train_loss']
            if not str(job_data['body']['measure']['f1']) == 'inf':
                doc['f1'] = job_data['body']['measure']['f1']
            es.index(index="dede_job_tracking_"+service_name.lower()+"_"+start_time, doc_type='data_point', body=doc)
        elif job_data['head']['status'] == 'finished':
            log_file.write("job running time "+str(job_data['head']['time'])+"\n")
            log_file.write("Iteration number "+str(job_data['body']['measure']['iteration'])+"\n")
            log_file.flush()
            running_time = job_data['head']['time']
            accp = job_data['body']['measure']['accp']
            recall = job_data['body']['measure']['recall']
            iteration = job_data['body']['measure']['iteration']
            precision = job_data['body']['measure']['precision']
            mcll = job_data['body']['measure']['mcll']
            f1 = job_data['body']['measure']['f1']
            #Get all data from job history and insert it.
            job_history = job_data['body']['measure_hist']
            total_length = len(job_history['iteration_hist'])
            for position in range(0,total_length):
                doc = {
                    'running_time': running_time,
                    'accp': job_history['accp_hist'][position],
                    'recall': job_history['recall_hist'][position],
                    'iteration': job_history['iteration_hist'][position],
                    'precision': job_history['precision_hist'][position],
                    'service_name': service_name,
                    'layers': layers,
                    'description': description,
                    'total_iterations': iterations,
                    'solver_type': solver_type,
                    'base_lr': base_lr,
                    'activation': activation,
                    'template': template,
                    'test_split': test_split,
                    'min_count': min_count,
                    'min_word_length': min_word_length,
                    'batch_size': batch_size,
                    'start_time': start_time,
                    'test_interval': test_interval,
                    'dataset_version': dataset_version,
                    'dataset_description': dataset_description
                }
                if not str(job_history['train_loss_hist'][position]) == 'inf':
                    doc['train_loss'] = job_history['train_loss_hist'][position]
                if not str(job_history['mcll_hist'][position]) == 'inf':
                    doc['mcll'] = job_history['mcll_hist'][position]
                if not str(job_history['f1_hist'][position]) == 'inf':
                    doc['f1'] = job_history['f1_hist'][position]
                es.index(index="dede_job_data_"+service_name.lower()+"_"+start_time, doc_type='data_point', body=doc)
            cmdiag = job_data['body']['measure']['cmdiag']
            #Insert last data point
            doc = {
                'running_time': running_time,
                'accp': accp,
                'recall': recall,
                'iteration': iteration,
                'precision': precision,
                'f1': f1,
                'service_name': service_name,
                'layers': layers,
                'description': description,
                'total_iterations': iterations,
                'solver_type': solver_type,
                'base_lr': base_lr,
                'activation': activation,
                'template': template,
                'test_split': test_split,
                'min_count': min_count,
                'min_word_length': min_word_length,
                'batch_size': batch_size,
                'start_time': start_time,
                'cmdiag': cmdiag,
                'test_interval': test_interval  ,
                'dataset_version': dataset_version,
                'dataset_description': dataset_description
            }
            if not str(job_data['body']['measure']['mcll']) == 'inf':
                doc['mcll'] = job_data['body']['measure']['mcll']
            if not str(job_data['body']['measure']['train_loss']) == 'inf':
                doc['train_loss'] = job_data['body']['measure']['train_loss']
            if not str(job_data['body']['measure']['f1']) == 'inf':
                doc['f1'] = job_data['body']['measure']['f1']
            es.index(index="dede_job_data_"+service_name.lower()+"_"+start_time, doc_type='data_point', body=doc)
            #store confusion matrix
            cmfull = job_data['body']['measure']['cmfull']
            for department in cmfull:
                department_name = department
                department_output = cmfull[department]
                doc = {
                    'running_time': running_time,
                    'department_name': department_name,
                    'department_output': department_output,
                    'service_name': service_name,
                    'layers': layers,
                    'description': description,
                    'total_iterations': iterations,
                    'solver_type': solver_type,
                    'base_lr': base_lr,
                    'activation': activation,
                    'template': template,
                    'test_split': test_split,
                    'min_count': min_count,
                    'min_word_length': min_word_length,
                    'batch_size': batch_size,
                    'start_time': start_time,
                    'test_interval': test_interval,
                    'dataset_version': dataset_version,
                    'dataset_description': dataset_description
                }
                es.index(index="dede_job_matrix_"+service_name.lower()+"_"+start_time, doc_type='matrix', body=doc)
            break
        sleep(10)
        count_job_data += 1

#Close log file
log_file.close()
