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
    public PetEntity savePet(String pName, char pGender, String pSpecies, Byte pAge, Integer pWeight,
                             String pSpec, char isMule, char isVaccin, String pBeforeInfo) {
        return petRepository.save(new PetEntity(pName, pGender, pSpecies, pAge, pWeight, pSpec, isMule, isVaccin, pBeforeInfo));
    }

    public List getAllPets() {
        return petRepository.findAll();
    }
}