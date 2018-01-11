import sys, os, datetime, time
import numpy as np
sys.path.append(os.path.abspath(os.path.join(os.path.dirname('.'), os.path.pardir)))
from src.testing import test_1D_torsion, test_pupil_detection, compare_torsion_results, test_eyelid_removal, test_2D_torsion
from src.helpers import manual_torsion_tracking
from src.gui import torsion_application
from src.data.data import Data
from src.torsion.xcorr2d import xcorr2d
from src.video import video as v
from src.iris.iris import iris_transform
from src.pupil.pupil import Pupil
from src.testing import test_eyelid_detection

'''
Main functions go here
'''
# test_1D_torsion.run_test()
# test_2D_torsion.run_test()
# test_pupil_detection.run_test()
# manual_torsion_tracking.main()
# compare_torsion_results.run_test()
# test_eyelid_removal.run_test()
# test_2D_torsion.run_test()
# torsion_application.run_test()
# test_eyelid_detection.run_test()

def transform(segment, resolution, window_height, mode='', **kw):

    # determine type of transform given mode
    if mode == 'upsample':
        return iris_transform(segment, Pupil(segment), window_height, theta_resolution=resolution)
    elif mode == 'eyelid':
        print('Eyelid Currently Not Implemented')
        return None
        # pupil = Pupil(segment)
        # seg = iris_transform(segment, pupil, window_height, theta_resolution=1)
        #
        # eyelid_mask = eyelid.detect_eyelid(segment, pupil, ROI_STRIP_WIDTH=100, ROI_BUFFER=5, POLY_TRANS=-10)
        # eyelid_mask = iris_transform(eyelid_mask, pupil, window_height, theta_resolution=1)
        # eyelid_mask_inv = eyelid_mask == 0
        #
        # seg = np.multiply(seg, eyelid_mask)
        # # mean = np.sum(seg)/(seg.size - len(np.where(eyelid_mask_inv)[0]))
        # mean = np.sum(seg)/seg.size
        # noise_seg = np.multiply(np.ones(seg.shape), mean)
        # # noise(seg.shape, mean)
        # seg = np.add(seg, np.multiply(eyelid_mask_inv, noise_seg))
        #
        # return seg
    else:
        return iris_transform(segment, Pupil(segment), window_height, theta_resolution=resolution)

def extend(image, diff=25):
    rows, cols = image.shape
    return np.concatenate((image[:,cols-diff:cols], image, image[:,0:diff]), axis=1)

def corr2d(video_path, verborose=True, **kw):

    # save all results to dictionary
    results = {
        'interp': {
            'full': [],
            'subset': []
        },
        'upsample': {
            'full': [],
            'subset': []
        },
        'standard': {
            'full': [],
            'subset': []
        }
    }

    # get parameters from kw args
    start_frame = kw.get('start_frame', 0)
    end_frame = kw.get('end_frame', -1)
    transform_resolution = kw.get('transform_resolution', 1)
    interp_resolution = kw.get('interp_resolution', 0.1)
    upsample_resolution = kw.get('upsample_resolution', 0.1)
    interp_threshold = kw.get('interp_threshold', 0.3)
    upsample_threshold = kw.get('upsample_threshold', 0)
    interp_start = kw.get('interp_start', 250)
    upsample_start = kw.get('upsample_start', 2500)
    window_length = kw.get('window_length', 50)
    window_height = kw.get('window_height', 30)
    max_angle = kw.get('max_angle', 25)
    pupil_threshold = kw.get('pupil_threshold', 10)
    im_crop = kw.get('im_crop', None) # List of crop indeces of form [row_lower_lim, row_upper_lim, col_lower_lim, col_upper_lim]

    video_name = os.path.basename(video_path)

    # save all results as data objects within in a folder
    now = datetime.datetime.now().strftime("%Y_%m_%d")
    file_path = os.path.abspath(os.path.join(os.curdir, 'results', video_name, now))

    if not os.path.isdir(file_path):
        os.makedirs(file_path)

    # create video object
    video = v.Video(video_path)

    metadata = kw
    # TODO add more?
    metadata['VIDEO_FPS'] = video.fps

    # create the reference windows
    first_frame = video[start_frame]

    # Crop the video frame
    if im_crop is not None:
        first_frame = first_frame[im_crop[0]:im_crop[1], im_crop[2]:im_crop[3]]

    iris_segment_interp = iris_transform(first_frame, Pupil(first_frame, threshold=pupil_threshold), window_height, theta_resolution=transform_resolution)
    iris_segment_upsample = iris_transform(first_frame, Pupil(first_frame, threshold=pupil_threshold), window_height, theta_resolution=upsample_resolution)

    reference_windows = {
        'interp': {
            'subset': iris_segment_interp[:, slice(interp_start,interp_start+window_length)],
            'extend': extend(iris_segment_interp, diff=max_angle)
        },
        'upsample': {
            'subset': iris_segment_upsample[:, slice(upsample_start,upsample_start+int(window_length/upsample_resolution))],
            'extend': extend(iris_segment_upsample, diff=int(max_angle/upsample_resolution))
        }
    }

    if verborose:
        print('Starting batch 2D Cross Correlation with upsample and interpolation ...')
        start_time = time.time()

    for segment in video[start_frame+1:end_frame]:
        # Crop frame
        if im_crop is not None:
            segment = segment[im_crop[0]:im_crop[1], im_crop[2]:im_crop[3]]
        # segment = segment[0:500, 500:1100]

        interp_seg = iris_transform(segment, Pupil(segment, threshold=pupil_threshold), window_height, theta_resolution=transform_resolution)
        upsample_seg = iris_transform(segment, Pupil(segment, threshold=pupil_threshold), window_height, theta_resolution=upsample_resolution)

        # standard method is upsampling with resolution 1
        t_standard_full = xcorr2d(interp_seg, reference_windows['interp']['extend'], 0, resolution=1, threshold=0, torsion_mode='upsample')
        t_standard_subset = xcorr2d(interp_seg, reference_windows['interp']['subset'], interp_start, resolution=1, threshold=-1, torsion_mode='upsample')
        t_interp_full = xcorr2d(interp_seg, reference_windows['interp']['extend'], 0, resolution=interp_resolution, threshold=interp_threshold, torsion_mode='interp')
        t_interp_subset = xcorr2d(interp_seg, reference_windows['interp']['subset'], interp_start, resolution=interp_resolution, threshold=interp_threshold, torsion_mode='interp')
        t_upsample_full = xcorr2d(upsample_seg, reference_windows['upsample']['extend'], 0, resolution=interp_resolution, threshold=interp_threshold, torsion_mode='upsample')
        t_upsample_subset = xcorr2d(upsample_seg, reference_windows['upsample']['subset'], upsample_start, resolution=upsample_resolution, threshold=upsample_threshold, torsion_mode='upsample')

        results['standard']['full'].append(t_standard_full)
        results['standard']['subset'].append(t_standard_subset)
        results['interp']['full'].append(t_interp_full)
        results['interp']['subset'].append(t_interp_subset)
        results['upsample']['full'].append(t_upsample_full)
        results['upsample']['subset'].append(t_upsample_subset)

        if verborose:
            print('Elapsed Time: {}s'.format(round(time.time() - start_time,2)), sep=' ', end='\r', flush=True)

    if verborose:
        print('Duration:', time.time() - start_time)

    for method in results:
        for mode in results[method]:
            obj = Data('_'.join((method, mode)), file_path)
            obj.set(results[method][mode], start_frame, metadata)
            obj.save()

            if verborose:
                print('Saving {} {} results.'.format(method, mode))