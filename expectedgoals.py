from settings import events, models
from math import log, exp, acos, hypot
from datetime import datetime
import rpy2.robjects as robjects
from rpy2.robjects.packages import importr

QUALIFIERS = [
    'Offensive', 'BigChance', 'Assisted', 'RightFoot', 'LeftFoot', 'Head', 'OtherBodyPart',
    'RegularPlay', 'FastBreak', 'SetPiece', 'FromCorner', 'Penalty', 'DirectFreekick', 'ThrowinSetPiece',
    ]


def geometry(x, y):
    point = (x, y)
    left, centre, right = (104, 34), (104, 38), (104, 42)

    distance = hypot(point[0] - centre[0], point[1] - centre[1])
    ldistance = hypot(point[0] - left[0], point[1] - left[1])
    rdistance = hypot(point[0] - right[0], point[1] - right[1])
    goalmouth = hypot(left[0] - right[0], left[1] - right[1])
    try:
        angle = acos(min(max((ldistance**2 + rdistance**2 - goalmouth**2) / (ldistance * rdistance * 2), -1), 1))
    except ValueError:
        angle = 0
        print(x, y)
        print((ldistance**2 + rdistance**2 - goalmouth**2) / (ldistance * rdistance * 2))
        exit()

    return distance, angle


def load_data(holdout=None):
    training = []
    validate = []

    for event in events.find({'isShot': True, 'isOwnGoal': {'$exists': False}}).limit(100000):
        shot = {
            'Goal': 1 if event.get('isGoal') else 0,
            'X': event['x'] * 1.04,
            'Y': event['y'] * 0.76,
        }
        shot['Lateral'] = abs(shot['Y'] - 38)
        shot['Distance'], shot['Angle'] = geometry(shot['X'], shot['Y'])

        shot_qualifiers = {q['type']['displayName'] for q in event['qualifiers']}
        for qualifier in QUALIFIERS:
            shot[qualifier] = 1 if qualifier in shot_qualifiers else 0

        # print(shot['id'], shot['id'] % 1)
        if holdout and event['id'] % holdout == 0:
            validate.append(shot)
            if len(validate) % 10000 == 0:
                print('{0} shots in validation set'.format(len(validate)))
        else:
            training.append(shot)
            if len(training) % 10000 == 0:
                print('{0} shots in training set'.format(len(training)))

    print('Shot retrieval complete')
    print('{0} shots in validation set'.format(len(validate)))
    print('{0} shots in training set'.format(len(training)))
    return training, validate


def run_logistic_regression(training, validate):
    df = dataset(training).get_dataframe()

    robjects.globalenv['shots'] = df
    robjects.r.save('shots', file='shots.rdata', compress=True)
    robjects.globalenv['shots'] = robjects.DataFrame({})

    variables = QUALIFIERS + ['X', 'Y', 'Lateral', 'Distance', 'Angle']

    full = robjects.r.formula('Goal~0+{0}'.format('+'.join(variables)))
    null = robjects.r.formula('Goal~1')

    stats = importr('stats')
    model = stats.glm(null, df, family='binomial')
    model = stats.step(model, scope=full, direction='both', trace=False)

    robjects.globalenv['xG'] = model
    robjects.r.save('xG', file='model-glm.rdata', compress=True)
    robjects.globalenv['xG'] = robjects.DataFrame({})

    # Validate
    df = dataset(validate).get_dataframe()
    xG = stats.predict(model, df)

    robjects.globalenv['glm'] = xG
    robjects.r.save('glm', file='xG-glm.rdata', compress=True)
    robjects.globalenv['glm'] = robjects.DataFrame({})

    # coefficients = {k: v for k, v in zip(model.rx2('coefficients').names, model.rx2('coefficients'))}
    # for k, v in coefficients.items():
    #     print('{0}: {1}'.format(k, v))
    # coefficients['Timestamp'] = datetime.now()
    # coefficients['Type'] = 'Logistic Regression'
    # models.save(coefficients)
    #
    # totals = {k: {'actual': 0, 'predicted': 0} for k in coefficients if k not in ['_id', 'Timestamp', 'Type', '(Intercept)']}
    # for shot in validate:
    #     scores = {k: v * shot.get(k, 1) for k, v in coefficients.items() if k not in ['_id', 'Timestamp', 'Type']}
    #     score = sum(scores.values())
    #     prediction = exp(score) / (1 + exp(score))
    #     shot['Scores'] = scores
    #     shot['Prediction'] = prediction
    #
    #     for k in totals:
    #         totals[k]['actual'] += shot['Goal'] if shot[k] else 0
    #         totals[k]['predicted'] += shot['Prediction'] if shot[k] else 0
    #
    # for k, v in totals.items():
    #     print('{0} - Actual: {1}, Predicted: {2:.1f}, Percentage: {3:.1%}'.format(k, v['actual'], v['predicted'], v['actual'] / v['predicted']))


def run_support_vector_machine(training, validate):
    # Train
    df = dataset(training).get_dataframe()

    robjects.globalenv['shots'] = df
    robjects.r.save('shots', file='shots.rdata', compress=True)
    robjects.globalenv['shots'] = robjects.DataFrame({})

    variables = QUALIFIERS + ['X', 'Y', 'Lateral', 'Distance', 'Angle']

    full = robjects.r.formula('Goal~0+{0}'.format('+'.join(variables)))
    null = robjects.r.formula('Goal~1')

    e1071 = importr('e1071')
    model = e1071.svm(null, df)

    robjects.globalenv['xG'] = model
    robjects.r.save('xG', file='model-svm.rdata', compress=True)
    robjects.globalenv['xG'] = robjects.DataFrame({})

    # Validate
    df = dataset(validate).get_dataframe()
    xG = e1071.predict.svm(model, df)

    robjects.globalenv['svm'] = xG
    robjects.r.save('svm', file='xG-svm.rdata', compress=True)
    robjects.globalenv['svm'] = robjects.DataFrame({})


def run_neural_network(training, validate):
    # Train
    df = dataset(training).get_dataframe()

    robjects.globalenv['shots'] = df
    robjects.r.save('shots', file='shots.rdata', compress=True)
    robjects.globalenv['shots'] = robjects.DataFrame({})

    variables = QUALIFIERS + ['X', 'Y', 'Lateral', 'Distance', 'Angle']

    full = robjects.r.formula('Goal~0+{0}'.format('+'.join(variables)))
    null = robjects.r.formula('Goal~1')

    neuralnet = importr('neuralnet')
    model = neuralnet.neuralnet(null, df)

    robjects.globalenv['xG'] = model
    robjects.r.save('xG', file='model-neuralnet.rdata', compress=True)
    robjects.globalenv['xG'] = robjects.DataFrame({})

    # Validate
    df = dataset(validate).get_dataframe()
    xG = neuralnet.compute(model, df)

    robjects.globalenv['neuralnet'] = xG
    robjects.r.save('neuralnet', file='xG-neuralnet.rdata', compress=True)
    robjects.globalenv['neuralnet'] = robjects.DataFrame({})


class dataset(object):
    def __init__(self, records=None):
        self.length = 0
        self.arrays = {}

        if records:
            for record in records:
                self.add_record(record)

    def add_record(self, record):
        for k in record:
            self.arrays.setdefault(k, [])

        for k in self.arrays:
            v = record.get(k, None)
            if type(v) not in [int, float]:
                print(type(v), v)
                print(record)
                exit()
            self.arrays[k].append(v)

        self.length += 1
        if self.length % 1000 == 0:
            print('{0} records loaded'.format(self.length))

    def get_dataframe(self):
        vectors = {}
        if self.length == 0:
            print('No data - generating empty data frame')
            return robjects.DataFrame(vectors)
        else:
            print('{0} records loaded'.format(self.length))

        for k, v in self.arrays.items():
            types = {type(element) for element in v if element is not None}
            if len(types) > 1:
                print('Multiple types found in column {}: {}'.format(k, types))
            elif str in types:
                vectors[k] = robjects.vectors.StrVector(v)
                # print('Converted column {} to StrVector'.format(k))
            elif int in types:
                vectors[k] = robjects.vectors.IntVector(v)
                # print('Converted column {} to IntVector'.format(k))
            elif float in types:
                vectors[k] = robjects.vectors.FloatVector(v)
                # print('Converted column {} to FloatVector'.format(k))
            else:
                print('Unknown type in column {}: {}'.format(k, ', '.join(types)))

        return robjects.DataFrame(vectors)


if __name__ == "__main__":
    training, validate = load_data()
    run_logistic_regression(training, training)
    run_support_vector_machine(training, training)
    run_neural_network(training, training)
