package com.smhrd.myapp.domain.pet;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class PetService {

    private final PetRepository petRepository;

    @Transactional
    public Long register(Long userId, String name, String species, Integer age) {
        PetEntity pet = PetEntity.builder()
                .userId(userId)
                .name(name)
                .species(species)
                .age(age)
                .build();
        return petRepository.save(pet).getId();
    }

    public List getPetsByUserId(Long userId) {
        return petRepository.findByUserId(userId);
    }
}