from zoltpy.quantile_io import BIN_DISTRIBUTION_CLASS, NAMED_DISTRIBUTION_CLASS, POINT_PREDICTION_CLASS, \
    SAMPLE_PREDICTION_CLASS


#
# csv_rows_from_json_io_dict()
#

CSV_HEADER = ['unit', 'target', 'class', 'value', 'cat', 'prob', 'sample', 'quantile', 'family', 'param1', 'param2',
              'param3']


def csv_rows_from_json_io_dict(json_io_dict):
    """
    A utility that converts a "JSON IO dict" as returned by zoltar to a list of zoltar-specific CSV row format. The
    columns are: 'unit', 'target', 'class', 'value', 'cat', 'prob', 'sample', 'quantile', 'family', 'param1', 'param2',
    'param3'. They are documented at https://docs.zoltardata.com/fileformats/#forecast-data-format-csv .

    :param json_io_dict: a "JSON IO dict" to load from. see docs for details. the "meta" section is ignored
    :return: a list of CSV rows including header - see CSV_HEADER
    """
    # do some initial validation
    if 'predictions' not in json_io_dict:
        raise RuntimeError("no predictions section found in json_io_dict")

    rows = [CSV_HEADER]  # return value. filled next
    for prediction_dict in json_io_dict['predictions']:
        prediction_class = prediction_dict['class']
        if prediction_class not in ['bin', 'named', 'point', 'sample', 'quantile']:
            raise RuntimeError(f"invalid prediction_dict class: {prediction_class}")

        unit = prediction_dict['unit']
        target = prediction_dict['target']
        prediction = prediction_dict['prediction']

        # class-specific columns all default to empty:
        value, cat, prob, sample, quantile, family, param1, param2, param3 = '', '', '', '', '', '', '', '', ''
        if prediction_class == BIN_DISTRIBUTION_CLASS:  # BinDistribution
            for cat, prob in zip(prediction['cat'], prediction['prob']):
                rows.append([unit, target, prediction_class, value, cat, prob, sample, quantile,
                             family, param1, param2, param3])
        elif prediction_class == NAMED_DISTRIBUTION_CLASS:  # NamedDistribution
            rows.append([unit, target, prediction_class, value, cat, prob, sample, quantile,
                         prediction['family'],
                         prediction['param1'] if 'param1' in prediction else '',
                         prediction['param2'] if 'param2' in prediction else '',
                         prediction['param3'] if 'param3' in prediction else ''])
        elif prediction_class == POINT_PREDICTION_CLASS:  # PointPrediction
            rows.append([unit, target, prediction_class, prediction['value'], cat, prob, sample, quantile,
                         family, param1, param2, param3])
        elif prediction_class == SAMPLE_PREDICTION_CLASS:  # SamplePrediction
            for sample in prediction['sample']:
                rows.append([unit, target, prediction_class, value, cat, prob, sample, quantile,
                             family, param1, param2, param3])
        else:  # prediction_class == QUANTILE_PREDICTION_CLASS  # QuantileDistribution
            for quantile, value in zip(prediction['quantile'], prediction['value']):
                rows.append([unit, target, prediction_class, value, cat, prob, sample, quantile,
                             family, param1, param2, param3])
    return rows
