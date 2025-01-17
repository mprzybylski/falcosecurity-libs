#!/usr/bin/env python3

import argparse
import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
pd.set_option('display.max_colwidth', None)
pd.set_option('display.max_rows', None, 'display.max_columns', None)

"""

Example Usage:
python3 plot_matrix.py --driver-artifacts-dir=/vm/build/driver_ok --save-png=/vm/build/driver_compat_matrix_success.png \
--title="Driver (clang -> bpf, gcc -> kmod) kernel compat matrix [compiled + success]" --hex-color="#3074EC";

"""


def arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--driver-artifacts-dir', help='Directory that contains subfolders by compiler version that contain the driver build artifact')
    parser.add_argument('--save-png', help='Plot output file path')
    parser.add_argument('--title', help='Title of output plot')
    parser.add_argument('--hex-color', help='Hex color reflecting success in output plot')
    return parser.parse_args()


def get_directory_listing(directory):
    if not os.path.exists(directory):
        exit()
    list_of_files = list()
    for (dirpath, dirnames, filenames) in os.walk(directory):
        list_of_files += [os.path.join(dirpath, file) for file in filenames if not '.DS' in file]
    if len(list_of_files) == 0:
        sys.exit('[Error] Directory {} is empty'.format(directory))
    return list_of_files


def get_pivoted_sorted_df(directory_compiler_driver):
    # Create pandas df based on the info about compiler, kernel version etc that is encoded in the path of the driver artifact, e.g. clang-12/5.19.0-051900-generic.o
    df_compiler_driver = pd.DataFrame(get_directory_listing(directory_compiler_driver), columns=['path'])
    df_compiler_driver['path_items'] = df_compiler_driver['path'].str.split(pat='\\/')
    df_compiler_driver['compiler'] = df_compiler_driver.apply(lambda x: x['path_items'][-2], axis=1)
    df_compiler_driver['compiler_type'] = df_compiler_driver['compiler'].str.extract(pat='(.*)-\\d{1,2}')
    df_compiler_driver['compiler_numeric'] = df_compiler_driver['compiler'].str.extract(pat='(\\d{1,2})').astype(float)
    df_compiler_driver['kernel_uname_r'] = df_compiler_driver.apply(lambda x: x['path_items'][-1], axis=1)
    df_compiler_driver['kernel_uname_r'] = df_compiler_driver['kernel_uname_r'].str.replace('(.ko|.o)', '', regex=True)
    df_compiler_driver['kernel_tmp'] = df_compiler_driver['kernel_uname_r'].str.split('.')
    df_compiler_driver['kernel_major'] = df_compiler_driver['kernel_tmp'].apply(lambda x: x[0]).astype(int)
    df_compiler_driver['kernel_minor'] = df_compiler_driver['kernel_tmp'].apply(lambda x: x[1]).astype(int)
    df_compiler_driver.sort_values(by=['kernel_major', 'kernel_minor'], inplace=True)
    kernels = df_compiler_driver['kernel_uname_r'].drop_duplicates(keep='last').values.tolist()
    df_compilers_sorted = df_compiler_driver.copy(deep=True).sort_values(by=['compiler_type','compiler_numeric'], inplace=False)
    compilers = df_compilers_sorted['compiler'].drop_duplicates(keep='last').values.tolist()

    # Need a df that has all compiler and kernel versions for subsequent outer SQL join
    kernels_compilers_list = []
    for kernel in kernels:
        for compiler in compilers:
            kernels_compilers_list.append((kernel, compiler))

    
    df_kernels_compiler = pd.DataFrame(kernels_compilers_list, columns=['kernel_uname_r', 'compiler'])
    df = pd.merge(df_compiler_driver, df_kernels_compiler, how='outer', on=['kernel_uname_r', 'compiler']).fillna(0)

    df['driver_ok'] = df['path']
    df['driver_ok'] = df.apply(lambda x: (100 if len(str(x['path'])) > 1 else 0), axis=1)

    df.sort_values(by=['kernel_uname_r', 'compiler'], inplace=True)
    df = df.pivot('kernel_uname_r', 'compiler', 'driver_ok')
    df = df.reindex(compilers, axis=1)
    df = df.reindex(kernels, axis=0)
    return df


def save_compatibility_plot(df, save_png_path, title, hex_color):
    plt.style.use('dark_background')
    plt.rcParams['figure.dpi'] = 1000
    plt.rcParams['savefig.dpi'] = 1000

    fig, ax = plt.subplots(1, 1, tight_layout=True, figsize=(12, 8))
    sns.heatmap(df.to_numpy(dtype=float),
                yticklabels=df.index,
                cmap=sns.color_palette(['#000000', hex_color], 2),
                vmin=0, vmax=100, linewidth=0.1, cbar_kws={'shrink': .8}, cbar=False)
    ax.set_xticklabels(df.columns, rotation=90, size=10)
    ax.set_yticklabels(df.index, rotation=0, size=10)
    ax.set_title('{}'.format(title), size=16)
    plt.savefig('{}'.format(save_png_path))


if __name__ == "__main__":
    args_parsed = arg_parser()
    df_pivoted_sorted = get_pivoted_sorted_df(args_parsed.driver_artifacts_dir)
    save_compatibility_plot(df_pivoted_sorted, args_parsed.save_png, args_parsed.title, args_parsed.hex_color)


