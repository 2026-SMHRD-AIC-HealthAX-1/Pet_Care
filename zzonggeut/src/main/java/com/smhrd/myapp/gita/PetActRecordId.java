package com.smhrd.myapp.gita;

import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;
import java.io.Serializable;
import java.time.LocalDateTime;

@NoArgsConstructor
@EqualsAndHashCode
public class PetActRecordId implements Serializable {
    private LocalDateTime dttm;
    private Integer petSeq;
}